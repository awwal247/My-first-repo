"""
app/routes/main.py
==================
UI navigation routes (authenticated):
  GET /          -- landing page (public)
  GET /menu      -- AI mode selection hub (now: full home dashboard)
  GET /chat      -- chat interface (requires login + mode)
  GET /select-mode/<mode_key>  -- set active AI mode
  GET /home      -- dashboard (alias for menu when logged in)
  GET /history   -- chat history page
  GET /memory    -- memory page
  GET /settings  -- settings page
  GET /profile   -- profile page
  GET /notifications -- notifications page
  GET /admin     -- admin page
  GET /files     -- files page
  GET /vision    -- vision AI page
  GET /research  -- deep research page
  GET /presentations -- presentations page
  GET /help      -- help page
  GET /modes     -- modes selection page
"""

from flask import (
    Blueprint, flash, redirect, render_template, session, url_for, request, jsonify
)

from app.config.ai_modes import AI_MODES
from app.utils.auth import time_based_greeting

main_bp = Blueprint("main", __name__)


def _require_login():
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))
    return None


@main_bp.route("/chat")
def index():
    redir = _require_login()
    if redir:
        return redir
    if "ai_mode" not in session:
        return redirect(url_for("main.modes"))

    mode_key = session["ai_mode"]
    mode = AI_MODES.get(mode_key, AI_MODES["researcher"])
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
@main_bp.route("/home")
def menu():
    redir = _require_login()
    if redir:
        return redir

    username = session.get("display_name") or session["user_id"]
    greeting = time_based_greeting(username)
    show_v21_disclaimer = session.pop("show_v21_disclaimer", False)
    current_mode_key = session.get("ai_mode", "")
    current_mode = AI_MODES.get(current_mode_key)

    return render_template(
        "menu.html",
        username=username,
        greeting=greeting,
        modes=AI_MODES,
        show_v21_disclaimer=show_v21_disclaimer,
        current_mode_key=current_mode_key,
        current_mode=current_mode,
    )


@main_bp.route("/select-mode/<mode_key>")
def select_mode(mode_key: str):
    redir = _require_login()
    if redir:
        return redir
    if mode_key not in AI_MODES:
        flash("Invalid AI mode.", "error")
        return redirect(url_for("main.modes"))
    session["ai_mode"] = mode_key
    return redirect(url_for("main.index"))


@main_bp.route("/modes")
def modes():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    current_mode_key = session.get("ai_mode", "")
    return render_template(
        "modes.html",
        username=username,
        modes=AI_MODES,
        current_mode_key=current_mode_key,
    )


@main_bp.route("/history")
def history():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    return render_template("history.html", username=username)


@main_bp.route("/memory")
def memory():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    return render_template("memory_page.html", username=username)


@main_bp.route("/settings")
def settings():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    return render_template("settings.html", username=username)


@main_bp.route("/profile")
def profile():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    user_email = session.get("email", "")
    return render_template("profile.html", username=username, user_email=user_email)


@main_bp.route("/notifications")
def notifications():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    return render_template("notifications.html", username=username)


@main_bp.route("/admin")
def admin():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    return render_template("admin.html", username=username)


@main_bp.route("/files")
def files():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    return render_template("files.html", username=username)


@main_bp.route("/vision")
def vision():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    return render_template("vision.html", username=username)


@main_bp.route("/research")
def research():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    return render_template("research.html", username=username)


@main_bp.route("/presentations")
def presentations():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    return render_template("presentations.html", username=username)


@main_bp.route("/help")
def help_page():
    redir = _require_login()
    if redir:
        return redir
    username = session.get("display_name") or session["user_id"]
    return render_template("help.html", username=username)
