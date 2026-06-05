"""
app/routes/main.py
==================
UI navigation routes (authenticated):
  GET /chat   -- chat interface (requires login + mode)
  GET /menu   -- AI mode selection
  GET /select-mode/<mode_key> -- set the active AI mode in the session
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    session,
    url_for,
)

from app.config.ai_modes import AI_MODES
from app.utils.auth import time_based_greeting

main_bp = Blueprint("main", __name__)


@main_bp.route("/chat")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))
    if "ai_mode" not in session:
        return redirect(url_for("main.menu"))

    mode_key = session["ai_mode"]
    mode     = AI_MODES.get(mode_key, AI_MODES["researcher"])
    username = session.get("display_name") or session["user_id"]
    greeting = time_based_greeting(username)

    return render_template(
        "index.html",
        username=username,
        greeting=greeting,
        mode=mode,
        mode_key=mode_key,
    )


@main_bp.route("/menu")
def menu():
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))

    username = session.get("display_name") or session["user_id"]
    greeting = time_based_greeting(username)

    return render_template(
        "menu.html",
        username=username,
        greeting=greeting,
        modes=AI_MODES,
    )


@main_bp.route("/select-mode/<mode_key>")
def select_mode(mode_key: str):
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))
    if mode_key not in AI_MODES:
        flash("Invalid AI mode.", "error")
        return redirect(url_for("main.menu"))

    session["ai_mode"] = mode_key
    return redirect(url_for("main.index"))
