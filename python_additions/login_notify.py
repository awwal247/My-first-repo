"""
ZENITH OX v2.7 — Login Notification System
============================================
Sends a notification for every single login, every time.
Includes: time/date, browser used, IP address, and best-effort location.

INTEGRATION — in your auth.py login route, AFTER successful login:
    from python_additions.login_notify import send_login_notification
    send_login_notification(supabase, user_id=str(user.id))

SUPABASE SQL — the notifications table should already exist.
If not, add this column/table as needed:
    -- Assumes a `notifications` table already exists with these columns:
    -- id, user_id, title, body, is_read, action_url, created_at
"""

from datetime import datetime, timezone
from flask import request


def get_client_ip() -> str:
    """Extract the real client IP, accounting for proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "Unknown"


def get_browser_info() -> str:
    """Extract a human-readable browser name from the User-Agent header."""
    ua = request.headers.get("User-Agent", "Unknown")
    ua_lower = ua.lower()

    if "edg" in ua_lower:
        return "Microsoft Edge"
    elif "chrome" in ua_lower:
        return "Google Chrome"
    elif "firefox" in ua_lower:
        return "Mozilla Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        return "Safari"
    elif "opera" in ua_lower or "opr" in ua_lower:
        return "Opera"
    elif "msie" in ua_lower or "trident" in ua_lower:
        return "Internet Explorer"
    else:
        # Return first 60 chars of raw UA as fallback
        return ua[:60]


def get_location_from_ip(ip: str) -> str:
    """
    Best-effort IP geolocation using a free API (ip-api.com).
    Falls back gracefully if the request fails or IP is private.
    """
    import socket

    # Skip lookup for private/loopback addresses
    private_prefixes = ("127.", "10.", "192.168.", "172.", "::1", "localhost")
    if any(ip.startswith(p) for p in private_prefixes):
        return "Local / Development"

    try:
        import urllib.request
        import json

        url = f"http://ip-api.com/json/{ip}?fields=status,city,regionName,country"
        with urllib.request.urlopen(url, timeout=2) as response:
            data = json.loads(response.read().decode())
            if data.get("status") == "success":
                parts = [data.get("city"), data.get("regionName"), data.get("country")]
                return ", ".join(p for p in parts if p)
    except Exception:
        pass

    return "Unknown location"


def send_login_notification(supabase, user_id: str) -> None:
    """
    Create a login security notification in the notifications table.
    Call this immediately after every successful login.
    """
    try:
        now = datetime.now(timezone.utc)
        ip = get_client_ip()
        browser = get_browser_info()
        location = get_location_from_ip(ip)

        time_str = now.strftime("%B %d, %Y at %I:%M %p UTC")

        title = "New Sign-In Detected"
        body = (
            f"Sign-in on {time_str}. "
            f"Browser: {browser}. "
            f"IP: {ip}. "
            f"Location: {location}."
        )

        supabase.table("notifications").insert({
            "user_id": user_id,
            "title": title,
            "body": body,
            "is_read": False,
            "action_url": "/notifications",
        }).execute()

    except Exception as e:
        print(f"[LoginNotify] Failed to send login notification: {e}")


def send_toast_and_notify(supabase, user_id: str, title: str, body: str,
                           action_url: str = "/notifications") -> dict:
    """
    Generic helper: store a notification in the DB AND return a toast payload.
    The Flask route should include the returned dict in its JSON response
    so the frontend can show the toast for 5 seconds.

    Usage in any route:
        toast = send_toast_and_notify(supabase, user_id, "Task Done", "Your export is ready.")
        return jsonify({"ok": True, ..., "toast": toast})
    """
    try:
        supabase.table("notifications").insert({
            "user_id": user_id,
            "title": title,
            "body": body,
            "is_read": False,
            "action_url": action_url,
        }).execute()
    except Exception as e:
        print(f"[LoginNotify] Failed to store notification: {e}")

    return {"title": title, "body": body, "action_url": action_url}
