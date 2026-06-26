"""
ZENITH OX v2.7 — Token Tracker
================================
Add this to your Flask app to enforce the 1,000 token/day limit for free users.

INTEGRATION:
1. Import and call `check_token_limit(user_id)` at the TOP of your /chat route,
   BEFORE any message is built or sent to the model.
2. Import and call `record_token_usage(user_id, tokens_used)` AFTER each
   successful model response (use the token count from the API response).
3. Add the `token_usage` table to your Supabase schema (SQL below).

SUPABASE SQL — run once in your Supabase SQL editor:
------------------------------------------------------
CREATE TABLE IF NOT EXISTS token_usage (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tokens      INTEGER NOT NULL DEFAULT 0,
    date        DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, date)
);
CREATE INDEX IF NOT EXISTS idx_token_usage_user_date ON token_usage(user_id, date);
------------------------------------------------------
"""

from datetime import date, datetime, timezone
from flask import session, redirect, url_for
from functools import wraps

FREE_DAILY_LIMIT = 1_000  # tokens per day for Basic plan


def get_today_token_usage(supabase, user_id: str) -> int:
    """Return how many tokens this user has used today."""
    try:
        today = date.today().isoformat()
        result = (
            supabase.table("token_usage")
            .select("tokens")
            .eq("user_id", user_id)
            .eq("date", today)
            .single()
            .execute()
        )
        return result.data.get("tokens", 0) if result.data else 0
    except Exception:
        return 0


def record_token_usage(supabase, user_id: str, tokens_used: int) -> int:
    """Add tokens_used to today's count. Returns new total."""
    try:
        today = date.today().isoformat()
        existing = get_today_token_usage(supabase, user_id)
        new_total = existing + tokens_used

        supabase.table("token_usage").upsert(
            {"user_id": user_id, "date": today, "tokens": new_total},
            on_conflict="user_id,date",
        ).execute()

        return new_total
    except Exception as e:
        print(f"[TokenTracker] Failed to record usage: {e}")
        return 0


def check_token_limit(supabase, user_id: str, is_premium: bool) -> dict:
    """
    Check if the user can still send a message.
    Returns: {"allowed": True/False, "used": int, "limit": int}

    Usage in your /chat route:
        check = check_token_limit(supabase, current_user.id, current_user.is_premium)
        if not check["allowed"]:
            return jsonify({"ok": False, "error": "token_limit",
                            "redirect": url_for("main.paywall")}), 429
    """
    if is_premium:
        return {"allowed": True, "used": 0, "limit": None}

    used = get_today_token_usage(supabase, user_id)
    return {
        "allowed": used < FREE_DAILY_LIMIT,
        "used": used,
        "limit": FREE_DAILY_LIMIT,
    }


# ── Decorator version (optional alternative) ─────────────────────────────────
def require_tokens(get_user_fn, get_supabase_fn):
    """
    Route decorator. Redirects to /paywall when token limit is exceeded.

    Usage:
        @app.route("/chat", methods=["POST"])
        @require_tokens(lambda: current_user, lambda: supabase)
        def chat():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_user_fn()
            supabase = get_supabase_fn()
            check = check_token_limit(supabase, str(user.id), getattr(user, "is_premium", False))
            if not check["allowed"]:
                from flask import request, jsonify
                if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({
                        "ok": False,
                        "error": "Daily token limit reached. Upgrade to Pro for unlimited access.",
                        "token_limit_exceeded": True,
                        "redirect": url_for("main.paywall"),
                    }), 429
                return redirect(url_for("main.paywall"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── Estimate tokens (simple heuristic until real count from API) ──────────────
def estimate_tokens(text: str) -> int:
    """Rough estimate: ~4 chars per token. Replace with actual API token count."""
    return max(1, len(text) // 4)
