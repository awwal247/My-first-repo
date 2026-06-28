"""
app/services/db.py
==================
Supabase / PostgreSQL database operations.

v5.0 UI/backend refresh additions:
  - Runtime schema bootstrap for existing + new product surfaces
  - Dashboard summary helpers
  - Profile and workspace settings persistence
  - Notification center persistence
  - User file vault persistence (BYTEA-backed)

Developer fallback (added):
  - If Supabase/Postgres is unreachable, calls that concern the shared
    developer/QA account (see app/services/fallback_db.py) are
    transparently retried against a local SQLite mirror instead of
    raising. Regular user accounts are unaffected and still see the
    real RuntimeError if the database is down. See fallback_db.py for
    the dev account's credentials and rationale.
"""

from __future__ import annotations

import functools
import json
import os
import threading
import uuid
from typing import Any
from urllib.parse import urlsplit

import psycopg2
from psycopg2.extras import RealDictCursor

from app.services import fallback_db as _fb

_SCHEMA_READY = False
_SCHEMA_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Developer-account fallback plumbing
# ---------------------------------------------------------------------------
#
# Maps each Postgres-backed db_* function name to its SQLite fallback_db.py
# equivalent (fb_*). Used by _with_dev_fallback() below.
_FALLBACK_MAP = {
    "db_find_user_by_email": _fb.fb_find_user_by_email,
    "db_find_user_by_id": _fb.fb_find_user_by_id,
    "db_update_user_profile": _fb.fb_update_user_profile,
    "db_update_user_password": _fb.fb_update_user_password,
    "db_save_message": _fb.fb_save_message,
    "db_get_conversation": _fb.fb_get_conversation,
    "db_clear_conversation": _fb.fb_clear_conversation,
    "db_get_all_modes_memory": _fb.fb_get_all_modes_memory,
    "db_create_chat": _fb.fb_create_chat,
    "db_get_chat": _fb.fb_get_chat,
    "db_get_user_chats": _fb.fb_get_user_chats,
    "db_update_chat": _fb.fb_update_chat,
    "db_delete_chat": _fb.fb_delete_chat,
    "db_toggle_pin": _fb.fb_toggle_pin,
    "db_rename_chat": _fb.fb_rename_chat,
    "db_search_chats": _fb.fb_search_chats,
    "db_restore_chat": _fb.fb_restore_chat,
    "db_get_or_create_user_settings": _fb.fb_get_or_create_user_settings,
    "db_update_user_settings": _fb.fb_update_user_settings,
    "db_get_dashboard_summary": _fb.fb_get_dashboard_summary,
    "db_create_notification": _fb.fb_create_notification,
    "db_get_user_notifications": _fb.fb_get_user_notifications,
    "db_mark_notification_read": _fb.fb_mark_notification_read,
    "db_mark_all_notifications_read": _fb.fb_mark_all_notifications_read,
    "db_delete_notification": _fb.fb_delete_notification,
    "db_save_user_file": _fb.fb_save_user_file,
    "db_get_user_files": _fb.fb_get_user_files,
    "db_get_user_file": _fb.fb_get_user_file,
    "db_delete_user_file": _fb.fb_delete_user_file,
}

# Functions whose first positional/keyword arg is a user_id (used to decide
# whether a failing call concerns the dev account).
_USER_ID_FIRST_ARG = {
    "db_find_user_by_id",
    "db_update_user_profile",
    "db_update_user_password",
    "db_save_message",
    "db_get_conversation",
    "db_clear_conversation",
    "db_get_all_modes_memory",
    "db_create_chat",
    "db_get_user_chats",
    "db_search_chats",
    "db_get_or_create_user_settings",
    "db_update_user_settings",
    "db_get_dashboard_summary",
    "db_create_notification",
    "db_get_user_notifications",
    "db_mark_notification_read",
    "db_mark_all_notifications_read",
    "db_delete_notification",
    "db_save_user_file",
    "db_get_user_files",
    "db_get_user_file",
    "db_delete_user_file",
}

# Functions keyed by chat_id rather than user_id -- we can't tell which
# user a chat belongs to without a lookup, so we ask the SQLite fallback
# directly whether it already knows this chat_id (i.e. it was created
# under the dev account).
_CHAT_KEYED_FUNCS = {"db_get_chat", "db_update_chat", "db_delete_chat", "db_toggle_pin", "db_rename_chat", "db_restore_chat"}


def _looks_like_dev_call(func_name: str, args: tuple, kwargs: dict) -> bool:
    """Best-effort check: does this call concern the shared dev account?"""
    if func_name == "db_find_user_by_email":
        email = (args[0] if args else kwargs.get("email")) or ""
        return _fb.is_dev_account(email=email)

    if func_name in _CHAT_KEYED_FUNCS:
        chat_id = (args[0] if args else kwargs.get("chat_id")) or ""
        try:
            return _fb.fb_get_chat(chat_id) is not None
        except Exception:
            return False

    if func_name in _USER_ID_FIRST_ARG:
        user_id = (args[0] if args else kwargs.get("user_id")) or ""
        return _fb.is_dev_account(user_id=user_id)

    return False


def _with_dev_fallback(func):
    """
    Decorator: on RuntimeError from the wrapped Postgres function, retry
    against the SQLite fallback IF the call concerns the dev account.
    Otherwise (or if it's not a dev-account call), re-raise the original
    error so real users still see accurate failures.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RuntimeError as exc:
            name = func.__name__
            fallback_fn = _FALLBACK_MAP.get(name)
            if fallback_fn and _looks_like_dev_call(name, args, kwargs):
                return fallback_fn(*args, **kwargs)
            raise exc

    return wrapper


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _validate_database_url(db_url: str) -> None:
    """Fail fast on missing or placeholder Supabase connection strings."""
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")

    parsed = urlsplit(db_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("DATABASE_URL must start with postgres:// or postgresql://")

    hostname = (parsed.hostname or "").strip()
    username = (parsed.username or "").strip()
    password = parsed.password

    if not hostname:
        raise RuntimeError("DATABASE_URL is missing a hostname")

    placeholder_detected = any(
        marker in db_url
        for marker in (
            "aws-0-.pooler.supabase.com",
            "db..supabase.co",
            "<project-ref>",
            "your-project-ref",
        )
    ) or username == "postgres." or ".." in hostname

    if placeholder_detected:
        raise RuntimeError(
            "DATABASE_URL still contains the example Supabase host/user placeholders. "
            "Copy the real Supabase connection string from Project Settings -> Database -> Connection string, "
            "use the Transaction pooler URI on port 6543 for Vercel, and URL-encode the password if it contains special characters."
        )

    if password in (None, ""):
        raise RuntimeError(
            "DATABASE_URL is missing the database password. Copy the full connection string from Supabase instead of editing the example by hand."
        )


def get_connection():
    """Create a fresh PostgreSQL connection from DATABASE_URL."""
    db_url = os.getenv("DATABASE_URL", "")
    _validate_database_url(db_url)
    try:
        return psycopg2.connect(db_url, connect_timeout=10, sslmode="require")
    except Exception as exc:
        raise RuntimeError(f"Database connection failed: {exc}") from exc


def close_connection(conn):
    """Safely close a connection."""
    if conn:
        conn.close()


# ---------------------------------------------------------------------------
# Runtime schema bootstrap
# ---------------------------------------------------------------------------

def ensure_runtime_schema(force: bool = False) -> None:
    """Create/upgrade the required tables for the refreshed UI if needed."""
    global _SCHEMA_READY
    if _SCHEMA_READY and not force:
        return

    with _SCHEMA_LOCK:
        if _SCHEMA_READY and not force:
            return

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE EXTENSION IF NOT EXISTS pgcrypto;

                    CREATE TABLE IF NOT EXISTS users (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email TEXT UNIQUE NOT NULL,
                        display_name TEXT NOT NULL,
                        password_hash TEXT,
                        google_id TEXT UNIQUE,
                        bio TEXT NOT NULL DEFAULT '',
                        avatar_color TEXT NOT NULL DEFAULT '#7c5cff',
                        created_at TIMESTAMPTZ DEFAULT now()
                    );

                    ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT NOT NULL DEFAULT '';
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_color TEXT NOT NULL DEFAULT '#7c5cff';

                    CREATE TABLE IF NOT EXISTS conversations (
                        id BIGSERIAL PRIMARY KEY,
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        mode_key TEXT NOT NULL,
                        role TEXT NOT NULL CHECK(role IN('user','assistant')),
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT now()
                    );

                    CREATE INDEX IF NOT EXISTS idx_conv_user_mode ON conversations(user_id, mode_key);

                    CREATE TABLE IF NOT EXISTS chats (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        title TEXT NOT NULL DEFAULT 'New chat',
                        mode TEXT NOT NULL DEFAULT 'researcher',
                        messages JSONB NOT NULL DEFAULT '[]',
                        pinned BOOLEAN NOT NULL DEFAULT false,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );

                    ALTER TABLE chats ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT false;
                    CREATE INDEX IF NOT EXISTS chats_user_id_updated_at ON chats(user_id, updated_at DESC);
                    CREATE INDEX IF NOT EXISTS chats_user_id_pinned ON chats(user_id, pinned DESC, updated_at DESC);

                    CREATE TABLE IF NOT EXISTS user_settings (
                        user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                        default_mode TEXT NOT NULL DEFAULT 'researcher',
                        email_notifications BOOLEAN NOT NULL DEFAULT true,
                        desktop_notifications BOOLEAN NOT NULL DEFAULT true,
                        auto_title_chats BOOLEAN NOT NULL DEFAULT true,
                        compact_mode BOOLEAN NOT NULL DEFAULT false,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS user_files (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        filename TEXT NOT NULL,
                        content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                        size_bytes BIGINT NOT NULL DEFAULT 0,
                        description TEXT NOT NULL DEFAULT '',
                        file_data BYTEA NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );

                    CREATE INDEX IF NOT EXISTS user_files_user_id_created_at ON user_files(user_id, created_at DESC);

                    CREATE TABLE IF NOT EXISTS notifications (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        title TEXT NOT NULL,
                        body TEXT NOT NULL,
                        category TEXT NOT NULL DEFAULT 'info',
                        is_read BOOLEAN NOT NULL DEFAULT false,
                        action_url TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );

                    CREATE INDEX IF NOT EXISTS notifications_user_id_created_at ON notifications(user_id, created_at DESC);
                    CREATE INDEX IF NOT EXISTS notifications_user_id_is_read ON notifications(user_id, is_read, created_at DESC);
                    """
                )
            conn.commit()
            _SCHEMA_READY = True
        except psycopg2.Error as exc:
            conn.rollback()
            raise RuntimeError(f"Could not bootstrap database schema: {exc}") from exc
        finally:
            close_connection(conn)


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def db_create_user(email: str, display_name: str, password_hash: str | None, google_id: str | None) -> dict:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO users (email, display_name, password_hash, google_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id, email, display_name, google_id, bio, avatar_color, created_at
                """,
                (email, display_name, password_hash, google_id),
            )
            result = cur.fetchone()
            conn.commit()
            return dict(result) if result else {}
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not create user: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_find_user_by_email(email: str) -> dict | None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            result = cur.fetchone()
            return dict(result) if result else None
    except psycopg2.Error as exc:
        raise RuntimeError(f"Database error: {exc}") from exc
    finally:
        close_connection(conn)


def db_find_user_by_google_id(google_id: str) -> dict | None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
            result = cur.fetchone()
            return dict(result) if result else None
    except psycopg2.Error as exc:
        raise RuntimeError(f"Database error: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_find_user_by_id(user_id: str) -> dict | None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            result = cur.fetchone()
            return dict(result) if result else None
    except psycopg2.Error as exc:
        raise RuntimeError(f"Database error: {exc}") from exc
    finally:
        close_connection(conn)


def db_link_google_id(user_id: str, google_id: str) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET google_id = %s WHERE id = %s",
                (google_id, user_id),
            )
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Database error: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_update_user_profile(user_id: str, display_name: str, bio: str, avatar_color: str) -> dict:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE users
                SET display_name = %s,
                    bio = %s,
                    avatar_color = %s
                WHERE id = %s
                RETURNING id, email, display_name, google_id, bio, avatar_color, created_at
                """,
                (display_name, bio, avatar_color, user_id),
            )
            result = cur.fetchone()
            conn.commit()
            return dict(result) if result else {}
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not update profile: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_update_user_password(user_id: str, password_hash: str) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (password_hash, user_id),
            )
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not update password: {exc}") from exc
    finally:
        close_connection(conn)


# ---------------------------------------------------------------------------
# Conversation operations (per-message memory)
# ---------------------------------------------------------------------------

@_with_dev_fallback
def db_save_message(user_id: str, mode_key: str, role: str, content: str) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (user_id, mode_key, role, content)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, mode_key, role, content),
            )
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not save message: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_get_conversation(user_id: str, mode_key: str, limit: int = 60) -> list[dict]:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT role, content, created_at
                FROM conversations
                WHERE user_id = %s AND mode_key = %s
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (user_id, mode_key, limit),
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not load conversation: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_clear_conversation(user_id: str, mode_key: str) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM conversations WHERE user_id = %s AND mode_key = %s",
                (user_id, mode_key),
            )
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not clear conversation: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_get_all_modes_memory(user_id: str) -> dict[str, list[dict]]:
    """Return all conversations grouped by mode_key."""
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT mode_key, role, content, created_at
                FROM conversations
                WHERE user_id = %s
                ORDER BY created_at ASC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            result: dict[str, list[dict]] = {}
            for row in rows:
                mk = row["mode_key"]
                result.setdefault(mk, []).append(dict(row))
            return result
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not load memory: {exc}") from exc
    finally:
        close_connection(conn)


# ---------------------------------------------------------------------------
# Chat session operations
# ---------------------------------------------------------------------------

@_with_dev_fallback
def db_create_chat(user_id: str, title: str, mode: str, messages: list) -> str:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        chat_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chats (id, user_id, title, mode, messages)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (chat_id, user_id, title, mode, json.dumps(messages)),
            )
            conn.commit()
            return chat_id
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not create chat: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_get_chat(chat_id: str) -> dict | None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM chats WHERE id = %s", (chat_id,))
            result = cur.fetchone()
            return dict(result) if result else None
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not load chat: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_get_user_chats(user_id: str, limit: int | None = None) -> list[dict]:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = (
                """
                SELECT id, title, mode, pinned, created_at, updated_at,
                       COALESCE(jsonb_array_length(messages), 0) AS message_count
                FROM chats
                WHERE user_id = %s
                ORDER BY pinned DESC, updated_at DESC
                """
            )
            params: list[Any] = [user_id]
            if limit is not None:
                query += " LIMIT %s"
                params.append(limit)
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not load chats: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_update_chat(chat_id: str, title: str | None = None, messages: list | None = None, mode: str | None = None) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            updates: list[str] = []
            params: list[Any] = []
            if title is not None:
                updates.append("title = %s")
                params.append(title)
            if messages is not None:
                updates.append("messages = %s")
                params.append(json.dumps(messages))
            if mode is not None:
                updates.append("mode = %s")
                params.append(mode)
            if not updates:
                return
            updates.append("updated_at = NOW()")
            params.append(chat_id)
            cur.execute(f"UPDATE chats SET {', '.join(updates)} WHERE id = %s", params)
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not update chat: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_delete_chat(chat_id: str) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chats WHERE id = %s", (chat_id,))
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not delete chat: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_toggle_pin(chat_id: str) -> bool:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chats SET pinned = NOT pinned, updated_at = NOW() WHERE id = %s RETURNING pinned",
                (chat_id,),
            )
            result = cur.fetchone()
            conn.commit()
            return result[0] if result else False
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not toggle pin: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_rename_chat(chat_id: str, new_title: str) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chats SET title = %s, updated_at = NOW() WHERE id = %s",
                (new_title, chat_id),
            )
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not rename chat: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_search_chats(user_id: str, query: str) -> list[dict]:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            search_pattern = f"%{query}%"
            cur.execute(
                """
                SELECT id, title, mode, pinned, created_at, updated_at,
                       COALESCE(jsonb_array_length(messages), 0) AS message_count
                FROM chats
                WHERE user_id = %s
                  AND (title ILIKE %s OR messages::text ILIKE %s)
                ORDER BY pinned DESC, updated_at DESC
                """,
                (user_id, search_pattern, search_pattern),
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not search chats: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_restore_chat(chat_id: str) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE chats SET updated_at = NOW() WHERE id = %s", (chat_id,))
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not restore chat: {exc}") from exc
    finally:
        close_connection(conn)


# ---------------------------------------------------------------------------
# Settings and dashboard helpers
# ---------------------------------------------------------------------------

@_with_dev_fallback
def db_get_or_create_user_settings(user_id: str) -> dict:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
            existing = cur.fetchone()
            if existing:
                return dict(existing)
            cur.execute(
                """
                INSERT INTO user_settings (user_id)
                VALUES (%s)
                RETURNING *
                """,
                (user_id,),
            )
            created = cur.fetchone()
            conn.commit()
            return dict(created) if created else {}
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not load user settings: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_update_user_settings(
    user_id: str,
    default_mode: str,
    email_notifications: bool,
    desktop_notifications: bool,
    auto_title_chats: bool,
    compact_mode: bool,
) -> dict:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO user_settings (
                    user_id, default_mode, email_notifications,
                    desktop_notifications, auto_title_chats, compact_mode, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    default_mode = EXCLUDED.default_mode,
                    email_notifications = EXCLUDED.email_notifications,
                    desktop_notifications = EXCLUDED.desktop_notifications,
                    auto_title_chats = EXCLUDED.auto_title_chats,
                    compact_mode = EXCLUDED.compact_mode,
                    updated_at = NOW()
                RETURNING *
                """,
                (
                    user_id,
                    default_mode,
                    email_notifications,
                    desktop_notifications,
                    auto_title_chats,
                    compact_mode,
                ),
            )
            result = cur.fetchone()
            conn.commit()
            return dict(result) if result else {}
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not update user settings: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_get_dashboard_summary(user_id: str) -> dict:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM chats WHERE user_id = %s) AS chat_count,
                    (SELECT COUNT(*) FROM chats WHERE user_id = %s AND updated_at >= NOW() - INTERVAL '7 days') AS chats_this_week,
                    (SELECT COUNT(*) FROM conversations WHERE user_id = %s) AS memory_count,
                    (SELECT COUNT(*) FROM user_files WHERE user_id = %s) AS file_count,
                    (SELECT COUNT(*) FROM notifications WHERE user_id = %s AND is_read = false) AS unread_notifications,
                    (SELECT COUNT(*) FROM chats WHERE user_id = %s AND pinned = true) AS pinned_chats
                """,
                (user_id, user_id, user_id, user_id, user_id, user_id),
            )
            result = cur.fetchone()
            return dict(result) if result else {}
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not load dashboard summary: {exc}") from exc
    finally:
        close_connection(conn)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@_with_dev_fallback
def db_create_notification(user_id: str, title: str, body: str, category: str = "info", action_url: str = "") -> str:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        notification_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notifications (id, user_id, title, body, category, action_url)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (notification_id, user_id, title, body, category, action_url),
            )
            conn.commit()
            return notification_id
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not create notification: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_get_user_notifications(user_id: str, limit: int = 50) -> list[dict]:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM notifications
                WHERE user_id = %s
                ORDER BY is_read ASC, created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not load notifications: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_mark_notification_read(user_id: str, notification_id: str) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE notifications SET is_read = true WHERE id = %s AND user_id = %s",
                (notification_id, user_id),
            )
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not mark notification as read: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_mark_all_notifications_read(user_id: str) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE notifications SET is_read = true WHERE user_id = %s", (user_id,))
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not mark all notifications as read: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_delete_notification(user_id: str, notification_id: str) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM notifications WHERE id = %s AND user_id = %s", (notification_id, user_id))
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not delete notification: {exc}") from exc
    finally:
        close_connection(conn)


# ---------------------------------------------------------------------------
# Files vault
# ---------------------------------------------------------------------------

@_with_dev_fallback
def db_save_user_file(
    user_id: str,
    filename: str,
    content_type: str,
    size_bytes: int,
    description: str,
    file_data: bytes,
) -> str:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        file_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_files (id, user_id, filename, content_type, size_bytes, description, file_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (file_id, user_id, filename, content_type, size_bytes, description, psycopg2.Binary(file_data)),
            )
            conn.commit()
            return file_id
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not save user file: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_get_user_files(user_id: str, limit: int = 100) -> list[dict]:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, filename, content_type, size_bytes, description, created_at
                FROM user_files
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not load user files: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_get_user_file(user_id: str, file_id: str) -> dict | None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, filename, content_type, size_bytes, description, file_data, created_at
                FROM user_files
                WHERE user_id = %s AND id = %s
                """,
                (user_id, file_id),
            )
            result = cur.fetchone()
            return dict(result) if result else None
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not load user file: {exc}") from exc
    finally:
        close_connection(conn)


@_with_dev_fallback
def db_delete_user_file(user_id: str, file_id: str) -> None:
    ensure_runtime_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_files WHERE user_id = %s AND id = %s", (user_id, file_id))
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not delete user file: {exc}") from exc
    finally:
        close_connection(conn)
