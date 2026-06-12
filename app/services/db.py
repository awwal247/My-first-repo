"""
app/services/db.py
==================
Supabase / PostgreSQL database operations.

v4.0 changes:
  - Added pinned column support in chats table
  - Added db_search_chats() for full-text search
  - Added db_toggle_pin() for pinning/unpinning chats
  - Added db_rename_chat() for inline rename
  - Added db_restore_chat() for restoring deleted/archived chats
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_connection():
    """Create a fresh PostgreSQL connection from DATABASE_URL."""
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    try:
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as exc:
        raise RuntimeError(f"Database connection failed: {exc}") from exc

def close_connection(conn):
    """Safely close a connection."""
    if conn:
        conn.close()

# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def db_create_user(email: str, display_name: str, password_hash: str | None, google_id: str | None) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO users (email, display_name, password_hash, google_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id, email, display_name, google_id, created_at
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

def db_find_user_by_email(email: str) -> dict | None:
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

def db_link_google_id(user_id: str, google_id: str) -> None:
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

# ---------------------------------------------------------------------------
# Conversation operations (per-message memory)
# ---------------------------------------------------------------------------

def db_save_message(user_id: str, mode_key: str, role: str, content: str) -> None:
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

def db_get_conversation(user_id: str, mode_key: str, limit: int = 60) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # FIX: get the NEWEST limit rows, returned in chrono order
            # (was ASC LIMIT → returned oldest N, cutting off recent context)
            cur.execute(
                """
                SELECT role, content, created_at FROM (
                    SELECT role, content, created_at
                    FROM conversations
                    WHERE user_id = %s AND mode_key = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                ) sub ORDER BY created_at ASC
                """,
                (user_id, mode_key, limit),
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not load conversation: {exc}") from exc
    finally:
        close_connection(conn)

def db_clear_conversation(user_id: str, mode_key: str) -> None:
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

def db_get_all_modes_memory(user_id: str) -> dict[str, list[dict]]:
    """Return all conversations grouped by mode_key."""
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
                if mk not in result:
                    result[mk] = []
                result[mk].append(dict(row))
            return result
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not load memory: {exc}") from exc
    finally:
        close_connection(conn)

# ---------------------------------------------------------------------------
# Chat session operations (chats table) — v4.0 with pinned support
# ---------------------------------------------------------------------------

def db_create_chat(user_id: str, title: str, mode: str, messages: list) -> str:
    """Create a new chat session and return its UUID."""
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

def db_get_chat(chat_id: str) -> dict | None:
    """Get a single chat by ID."""
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

def db_get_user_chats(user_id: str) -> list[dict]:
    """Get all chats for a user, sorted by pinned first then updated_at desc."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, title, mode, pinned, created_at, updated_at,
                       COALESCE(jsonb_array_length(messages), 0) as message_count
                FROM chats
                WHERE user_id = %s
                ORDER BY pinned DESC, updated_at DESC
                """,
                (user_id,),
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not load chats: {exc}") from exc
    finally:
        close_connection(conn)

def db_update_chat(chat_id: str, title: str | None = None, messages: list | None = None, mode: str | None = None) -> None:
    """Update a chat's title, messages, and/or mode."""
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
            cur.execute(
                f"UPDATE chats SET {', '.join(updates)} WHERE id = %s",
                params,
            )
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not update chat: {exc}") from exc
    finally:
        close_connection(conn)

def db_delete_chat(chat_id: str) -> None:
    """Permanently delete a chat session."""
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

# v4.0 — Pin / unpin a chat

def db_toggle_pin(chat_id: str) -> bool:
    """Toggle the pinned state of a chat. Returns the new pinned value."""
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

# v4.0 — Rename a chat

def db_rename_chat(chat_id: str, new_title: str) -> None:
    """Rename a chat session."""
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

# v4.0 — Search chats

def db_search_chats(user_id: str, query: str) -> list[dict]:
    """Search user's chats by title or message content."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            search_pattern = f"%{query}%"
            cur.execute(
                """
                SELECT id, title, mode, pinned, created_at, updated_at,
                       COALESCE(jsonb_array_length(messages), 0) as message_count
                FROM chats
                WHERE user_id = %s
                  AND (
                      title ILIKE %s
                      OR messages::text ILIKE %s
                  )
                ORDER BY pinned DESC, updated_at DESC
                """,
                (user_id, search_pattern, search_pattern),
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as exc:
        raise RuntimeError(f"Could not search chats: {exc}") from exc
    finally:
        close_connection(conn)

# v4.0 — Restore chat (update timestamp to bring to top)

def db_restore_chat(chat_id: str) -> None:
    """Restore a chat by bumping its updated_at timestamp."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chats SET updated_at = NOW() WHERE id = %s",
                (chat_id,),
            )
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        raise RuntimeError(f"Could not restore chat: {exc}") from exc
    finally:
        close_connection(conn)
