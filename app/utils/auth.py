"""
app/utils/auth.py
=================
Authentication helper functions:
  - Email validation
  - User lookup helpers (now backed by Supabase via db.py)
  - Display-name derivation
  - Time-based greeting
"""

import re
from datetime import datetime

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(email: str) -> bool:
    """Return True if email matches a basic e-mail pattern."""
    return bool(_EMAIL_RE.match(email or ""))


def find_user_by_email(email: str) -> tuple[str | None, dict | None]:
    """
    Search the database for a user with a matching e-mail address.

    Returns (str(user_id), user_dict) if found, else (None, None).
    """
    email = (email or "").strip().lower()
    try:
        from app.services.db import db_find_user_by_email
        user = db_find_user_by_email(email)
    except RuntimeError:
        return None, None

    if user is None:
        return None, None
    return str(user["id"]), user


def find_user_by_google_id(gid: str) -> tuple[str | None, dict | None]:
    """
    Search the database for a user with a matching Google OAuth sub.

    Returns (str(user_id), user_dict) if found, else (None, None).
    """
    try:
        from app.services.db import db_find_user_by_google_id
        user = db_find_user_by_google_id(gid)
    except RuntimeError:
        return None, None

    if user is None:
        return None, None
    return str(user["id"]), user


def display_name_from_email(email: str) -> str:
    """Derive a friendly display name from an e-mail local part."""
    return (email or "").split("@")[0] or "friend"


def time_based_greeting(name: str) -> str:
    """
    Return a time-appropriate greeting for name.

    Greeting changes at 05:00, 12:00, 17:00, and 22:00.
    """
    hour = datetime.now().hour
    if 5 <= hour < 12:
        part = "Good morning"
    elif 12 <= hour < 17:
        part = "Good afternoon"
    elif 17 <= hour < 22:
        part = "Good evening"
    else:
        part = "Good night"
    return f"{part}, {name}"
