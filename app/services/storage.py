"""
app/services/storage.py
=======================
Simple in-memory user memory storage using Flask session.
Provides get_user_memory and update_user_memory for quick
access without hitting the database on every read.
"""

from flask import session

def _make_key(memory_key: str) -> str:
    return f"_zenith_mem_{memory_key}"

def get_user_memory(memory_key: str) -> list[dict]:
    """
    Get the recent conversation history for a user+mode combination.
    Returns a list of {"role": ..., "content": ...} dicts.
    """
    key = _make_key(memory_key)
    return session.get(key, [])

def update_user_memory(memory_key: str, role: str, content: str) -> None:
    """
    Append a message to the in-memory conversation history.
    Trims to the last 30 messages to keep session size reasonable.
    """
    key = _make_key(memory_key)
    history = session.get(key, [])
    history.append({"role": role, "content": content})
    # Keep only last 30 messages
    if len(history) > 30:
        history = history[-30:]
    session[key] = history
    session.modified = True
