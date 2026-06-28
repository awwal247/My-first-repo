"""
app/services/fallback_db.py
============================
Local SQLite fallback store — keeps ONE shared developer/test account
working even when Supabase/Postgres (DATABASE_URL) is unreachable.

Why this exists
----------------
Zenith OX normally stores everything in Supabase Postgres. If Supabase
has an outage, is misconfigured, or DATABASE_URL is wrong, every db_*
call in app/services/db.py raises RuntimeError and the whole app (login,
chat, history) becomes unusable -- which is a problem when a developer
needs to demo or test the app regardless of backend status.

This module provides a small, self-contained SQLite mirror of the same
tables (users / chats / conversations / notifications / user_settings)
that lives on local disk at app/services/zenith_fallback.db. It is used
ONLY for the single fixed developer account below -- regular user
accounts are never written here and always go through real Postgres.

Developer / QA account (shared, NOT a real user)
--------------------------------------------------
  email:    dev@zenithox.local
  password: PIPuTZdEZyGlxw
  user_id:  ecb548c8-436b-5ef0-9250-2aa36942bcb3   (fixed, stable UUID)

This account is auto-created in the SQLite fallback file the first time
this module is imported, and is ALSO inserted into Supabase itself (see
schema.sql) so it exists as a normal row there too, on the off chance
Supabase is up but something else is wrong. Share these credentials only
with other developers on the team -- never give them to end users.

Persistence note: the SQLite file lives on local disk. On Vercel
(serverless, ephemeral filesystem) this file is recreated fresh on each
cold start -- the dev account itself is always re-seeded automatically,
but any chats/messages created while testing will not persist across
deploys or cold starts. That trade-off is intentional: the goal here is
"the dev account always logs in and the chat UI always works", not long
-term storage. For durable cross-deploy storage, fix the real
DATABASE_URL / Supabase connection instead.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# Fixed developer account constants
# ---------------------------------------------------------------------------

DEV_USER_ID = "ecb548c8-436b-5ef0-9250-2aa36942bcb3"
DEV_EMAIL = "dev@zenithox.local"
DEV_PASSWORD = "PIPuTZdEZyGlxw"  # shared dev/QA credential -- see module docstring
DEV_DISPLAY_NAME = "Zenith Dev"

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zenith_fallback.db")
_LOCK = threading.Lock()
_READY = False


def is_dev_account(user_id: str | None = None, email: str | None = None) -> bool:
    """True if the given user_id or email refers to the shared dev/test account."""
    if user_id and str(user_id) == DEV_USER_ID:
        return True
    if email and email.strip().lower() == DEV_EMAIL:
        return True
    return False


# ---------------------------------------------------------------------------
# Connection + schema bootstrap
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_schema() -> None:
    global _READY
    if _READY:
        return
    with _LOCK:
        if _READY:
            return
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    password_hash TEXT,
                    google_id TEXT UNIQUE,
                    bio TEXT NOT NULL DEFAULT '',
                    avatar_color TEXT NOT NULL DEFAULT '#c9a84c',
                    is_premium INTEGER NOT NULL DEFAULT 1,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    mode_key TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT 'New chat',
                    mode TEXT NOT NULL DEFAULT 'researcher',
                    messages TEXT NOT NULL DEFAULT '[]',
                    pinned INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    default_mode TEXT NOT NULL DEFAULT 'researcher',
                    email_notifications INTEGER NOT NULL DEFAULT 1,
                    desktop_notifications INTEGER NOT NULL DEFAULT 1,
                    auto_title_chats INTEGER NOT NULL DEFAULT 1,
                    compact_mode INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_files (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    description TEXT NOT NULL DEFAULT '',
                    file_data BLOB NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'info',
                    is_read INTEGER NOT NULL DEFAULT 0,
                    action_url TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
            _seed_dev_user(conn)
            _READY = True
        finally:
            conn.close()


def _seed_dev_user(conn: sqlite3.Connection) -> None:
    """Insert the fixed dev account + welcome notification if not already present."""
    existing = conn.execute("SELECT id FROM users WHERE id = ?", (DEV_USER_ID,)).fetchone()
    if existing:
        return
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO users (id, email, display_name, password_hash, google_id,
                            bio, avatar_color, is_premium, is_admin, created_at)
        VALUES (?, ?, ?, ?, NULL, ?, ?, 1, 0, ?)
        """,
        (
            DEV_USER_ID,
            DEV_EMAIL,
            DEV_DISPLAY_NAME,
            generate_password_hash(DEV_PASSWORD),
            "Shared developer/QA account. Works even when Supabase is down.",
            "#c9a84c",
            now,
        ),
    )
    conn.execute(
        "INSERT INTO user_settings (user_id, updated_at) VALUES (?, ?)",
        (DEV_USER_ID, now),
    )
    conn.execute(
        """
        INSERT INTO notifications (id, user_id, title, body, category, is_read, action_url, created_at)
        VALUES (?, ?, ?, ?, ?, 0, '', ?)
        """,
        (
            str(uuid.uuid4()),
            DEV_USER_ID,
            "Running on local fallback storage",
            "Supabase was unreachable, so this developer account is currently backed by a "
            "local SQLite file instead of Postgres. Chat history here will not sync across deploys.",
            "info",
            now,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def fb_find_user_by_email(email: str) -> dict | None:
    _ensure_schema()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fb_find_user_by_id(user_id: str) -> dict | None:
    _ensure_schema()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fb_update_user_profile(user_id: str, display_name: str, bio: str, avatar_color: str) -> dict:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE users SET display_name = ?, bio = ?, avatar_color = ? WHERE id = ?",
            (display_name, bio, avatar_color, user_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def fb_update_user_password(user_id: str, password_hash: str) -> None:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Conversation (per-message memory) operations
# ---------------------------------------------------------------------------

def fb_save_message(user_id: str, mode_key: str, role: str, content: str) -> None:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO conversations (user_id, mode_key, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, mode_key, role, content, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def fb_get_conversation(user_id: str, mode_key: str, limit: int = 60) -> list[dict]:
    _ensure_schema()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT role, content, created_at FROM conversations
            WHERE user_id = ? AND mode_key = ?
            ORDER BY created_at ASC LIMIT ?
            """,
            (user_id, mode_key, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fb_clear_conversation(user_id: str, mode_key: str) -> None:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute(
            "DELETE FROM conversations WHERE user_id = ? AND mode_key = ?",
            (user_id, mode_key),
        )
        conn.commit()
    finally:
        conn.close()


def fb_get_all_modes_memory(user_id: str) -> dict[str, list[dict]]:
    _ensure_schema()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT mode_key, role, content, created_at FROM conversations
            WHERE user_id = ? ORDER BY created_at ASC
            """,
            (user_id,),
        ).fetchall()
        result: dict[str, list[dict]] = {}
        for row in rows:
            d = dict(row)
            result.setdefault(d["mode_key"], []).append(d)
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Chat session operations
# ---------------------------------------------------------------------------

def fb_create_chat(user_id: str, title: str, mode: str, messages: list) -> str:
    _ensure_schema()
    conn = _connect()
    try:
        chat_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO chats (id, user_id, title, mode, messages, pinned, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
            (chat_id, user_id, title, mode, json.dumps(messages), now, now),
        )
        conn.commit()
        return chat_id
    finally:
        conn.close()


def fb_get_chat(chat_id: str) -> dict | None:
    _ensure_schema()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["messages"] = json.loads(d["messages"] or "[]")
        d["pinned"] = bool(d["pinned"])
        return d
    finally:
        conn.close()


def fb_get_user_chats(user_id: str, limit: int | None = None) -> list[dict]:
    _ensure_schema()
    conn = _connect()
    try:
        query = (
            "SELECT id, title, mode, pinned, created_at, updated_at, messages FROM chats "
            "WHERE user_id = ? ORDER BY pinned DESC, updated_at DESC"
        )
        params: list = [user_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(query, params).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            try:
                d["message_count"] = len(json.loads(d.pop("messages") or "[]"))
            except Exception:
                d["message_count"] = 0
            d["pinned"] = bool(d["pinned"])
            out.append(d)
        return out
    finally:
        conn.close()


def fb_update_chat(chat_id: str, title: str | None = None, messages: list | None = None, mode: str | None = None) -> None:
    _ensure_schema()
    conn = _connect()
    try:
        updates, params = [], []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if messages is not None:
            updates.append("messages = ?")
            params.append(json.dumps(messages))
        if mode is not None:
            updates.append("mode = ?")
            params.append(mode)
        if not updates:
            return
        updates.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(chat_id)
        conn.execute(f"UPDATE chats SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    finally:
        conn.close()


def fb_delete_chat(chat_id: str) -> None:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        conn.commit()
    finally:
        conn.close()


def fb_toggle_pin(chat_id: str) -> bool:
    _ensure_schema()
    conn = _connect()
    try:
        row = conn.execute("SELECT pinned FROM chats WHERE id = ?", (chat_id,)).fetchone()
        if not row:
            return False
        new_val = 0 if row["pinned"] else 1
        conn.execute(
            "UPDATE chats SET pinned = ?, updated_at = ? WHERE id = ?",
            (new_val, datetime.now(timezone.utc).isoformat(), chat_id),
        )
        conn.commit()
        return bool(new_val)
    finally:
        conn.close()


def fb_rename_chat(chat_id: str, new_title: str) -> None:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
            (new_title, datetime.now(timezone.utc).isoformat(), chat_id),
        )
        conn.commit()
    finally:
        conn.close()


def fb_search_chats(user_id: str, query: str) -> list[dict]:
    _ensure_schema()
    conn = _connect()
    try:
        pattern = f"%{query}%"
        rows = conn.execute(
            """
            SELECT id, title, mode, pinned, created_at, updated_at, messages FROM chats
            WHERE user_id = ? AND (title LIKE ? OR messages LIKE ?)
            ORDER BY pinned DESC, updated_at DESC
            """,
            (user_id, pattern, pattern),
        ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            try:
                d["message_count"] = len(json.loads(d.pop("messages") or "[]"))
            except Exception:
                d["message_count"] = 0
            d["pinned"] = bool(d["pinned"])
            out.append(d)
        return out
    finally:
        conn.close()


def fb_restore_chat(chat_id: str) -> None:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE chats SET updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), chat_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Settings + dashboard
# ---------------------------------------------------------------------------

def fb_get_or_create_user_settings(user_id: str) -> dict:
    _ensure_schema()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            d = dict(row)
        else:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT INTO user_settings (user_id, updated_at) VALUES (?, ?)", (user_id, now))
            conn.commit()
            row = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
            d = dict(row)
        for key in ("email_notifications", "desktop_notifications", "auto_title_chats", "compact_mode"):
            d[key] = bool(d[key])
        return d
    finally:
        conn.close()


def fb_update_user_settings(
    user_id: str,
    default_mode: str,
    email_notifications: bool,
    desktop_notifications: bool,
    auto_title_chats: bool,
    compact_mode: bool,
) -> dict:
    _ensure_schema()
    conn = _connect()
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO user_settings (user_id, default_mode, email_notifications,
                                        desktop_notifications, auto_title_chats, compact_mode, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                default_mode = excluded.default_mode,
                email_notifications = excluded.email_notifications,
                desktop_notifications = excluded.desktop_notifications,
                auto_title_chats = excluded.auto_title_chats,
                compact_mode = excluded.compact_mode,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                default_mode,
                int(bool(email_notifications)),
                int(bool(desktop_notifications)),
                int(bool(auto_title_chats)),
                int(bool(compact_mode)),
                now,
            ),
        )
        conn.commit()
        return fb_get_or_create_user_settings(user_id)
    finally:
        conn.close()


def fb_get_dashboard_summary(user_id: str) -> dict:
    _ensure_schema()
    conn = _connect()
    try:
        chat_count = conn.execute("SELECT COUNT(*) FROM chats WHERE user_id = ?", (user_id,)).fetchone()[0]
        memory_count = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        file_count = conn.execute("SELECT COUNT(*) FROM user_files WHERE user_id = ?", (user_id,)).fetchone()[0]
        unread = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,)
        ).fetchone()[0]
        pinned = conn.execute(
            "SELECT COUNT(*) FROM chats WHERE user_id = ? AND pinned = 1", (user_id,)
        ).fetchone()[0]
        return {
            "chat_count": chat_count,
            "chats_this_week": chat_count,
            "memory_count": memory_count,
            "file_count": file_count,
            "unread_notifications": unread,
            "pinned_chats": pinned,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def fb_create_notification(user_id: str, title: str, body: str, category: str = "info", action_url: str = "") -> str:
    _ensure_schema()
    conn = _connect()
    try:
        notif_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO notifications (id, user_id, title, body, category, is_read, action_url, created_at) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
            (notif_id, user_id, title, body, category, action_url, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return notif_id
    finally:
        conn.close()


def fb_get_user_notifications(user_id: str, limit: int = 50) -> list[dict]:
    _ensure_schema()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY is_read ASC, created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["is_read"] = bool(d["is_read"])
            out.append(d)
        return out
    finally:
        conn.close()


def fb_mark_notification_read(user_id: str, notification_id: str) -> None:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (notification_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def fb_mark_all_notifications_read(user_id: str) -> None:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def fb_delete_notification(user_id: str, notification_id: str) -> None:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute("DELETE FROM notifications WHERE id = ? AND user_id = ?", (notification_id, user_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Files vault
# ---------------------------------------------------------------------------

def fb_save_user_file(user_id: str, filename: str, content_type: str, size_bytes: int,
                       description: str, file_data: bytes) -> str:
    _ensure_schema()
    conn = _connect()
    try:
        file_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO user_files (id, user_id, filename, content_type, size_bytes, description, "
            "file_data, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (file_id, user_id, filename, content_type, size_bytes, description,
             sqlite3.Binary(file_data), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return file_id
    finally:
        conn.close()


def fb_get_user_files(user_id: str, limit: int = 100) -> list[dict]:
    _ensure_schema()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, filename, content_type, size_bytes, description, created_at FROM user_files "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fb_get_user_file(user_id: str, file_id: str) -> dict | None:
    _ensure_schema()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, filename, content_type, size_bytes, description, file_data, created_at "
            "FROM user_files WHERE user_id = ? AND id = ?",
            (user_id, file_id),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["file_data"] = bytes(d["file_data"])
        return d
    finally:
        conn.close()


def fb_delete_user_file(user_id: str, file_id: str) -> None:
    _ensure_schema()
    conn = _connect()
    try:
        conn.execute("DELETE FROM user_files WHERE user_id = ? AND id = ?", (user_id, file_id))
        conn.commit()
    finally:
        conn.close()


# Bootstrap immediately on import so the dev account always exists,
# even before the first request comes in.
_ensure_schema()
