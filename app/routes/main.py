"""
app/routes/main.py
==================
UI navigation routes (authenticated):
  GET /chat -- chat interface (requires login + mode)
  GET /menu, /dashboard -- dashboard / AI mode selection
  GET /select-mode/<mode_key> -- set the active AI mode in the session
  GET/POST /profile -- manage profile information
  GET/POST /settings -- manage workspace preferences
  GET/POST /files -- upload and manage vault files
  GET /history-center -- chat history management surface
  GET /notifications -- notification center
"""

from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from app.config.ai_modes import AI_MODES
from app.config.chat_models import DEFAULT_CHAT_MODEL_KEY, get_chat_models_for_ui
from app.services.db import (
    db_create_notification,
    db_delete_chat,
    db_delete_notification,
    db_delete_user_file,
    db_find_user_by_id,
    db_get_chat,
    db_get_dashboard_summary,
    db_get_or_create_user_settings,
    db_get_user_file,
    db_get_user_files,
    db_get_user_notifications,
    db_get_user_chats,
    db_mark_all_notifications_read,
    db_mark_notification_read,
    db_restore_chat,
    db_save_user_file,
    db_search_chats,
    db_toggle_pin,
    db_update_user_password,
    db_update_user_profile,
    db_update_user_settings,
)
from app.utils.auth import time_based_greeting
from app.utils.files import MAX_UPLOAD_SIZE

main_bp = Blueprint("main", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_auth_redirect():
    if "user_id" not in session:
        return None, redirect(url_for("auth.login_page"))
    user = db_find_user_by_id(session["user_id"])
    if not user:
        session.clear()
        return None, redirect(url_for("auth.login_page"))
    return user, None


def _dashboard_context(user: dict) -> dict:
    username = user.get("display_name") or session.get("display_name") or session["user_id"]
    greeting = time_based_greeting(username)
    settings = db_get_or_create_user_settings(str(user["id"]))
    summary = db_get_dashboard_summary(str(user["id"]))
    recent_chats = db_get_user_chats(str(user["id"]), limit=6)
    notifications = db_get_user_notifications(str(user["id"]), limit=6)
    return {
        "username": username,
        "greeting": greeting,
        "settings": settings,
        "dashboard_summary": summary,
        "recent_chats": recent_chats,
        "recent_notifications": notifications,
        "unread_notifications": summary.get("unread_notifications", 0),
        "user": user,
    }


# ---------------------------------------------------------------------------
# Core app pages
# ---------------------------------------------------------------------------

@main_bp.route("/chat")
def index():
    user, err = _require_auth_redirect()
    if err:
        return err
    if "ai_mode" not in session:
        settings = db_get_or_create_user_settings(str(user["id"]))
        session["ai_mode"] = settings.get("default_mode", "researcher")

    mode_key = session["ai_mode"]
    mode = AI_MODES.get(mode_key, AI_MODES["researcher"])
    username = user.get("display_name") or session["user_id"]
    greeting = time_based_greeting(username)
    summary = db_get_dashboard_summary(str(user["id"]))

    available_chat_models = get_chat_models_for_ui()
    selected_chat_model_key = session.get("chat_model_key", DEFAULT_CHAT_MODEL_KEY)
    if selected_chat_model_key not in available_chat_models:
        selected_chat_model_key = DEFAULT_CHAT_MODEL_KEY
        session["chat_model_key"] = selected_chat_model_key

    return render_template(
        "index.html",
        username=username,
        greeting=greeting,
        mode=mode,
        mode_key=mode_key,
        unread_notifications=summary.get("unread_notifications", 0),
        file_count=summary.get("file_count", 0),
        available_chat_models=available_chat_models,
        selected_chat_model_key=selected_chat_model_key,
    )


@main_bp.route("/menu")
@main_bp.route("/dashboard")
def menu():
    user, err = _require_auth_redirect()
    if err:
        return err

    ctx = _dashboard_context(user)
    show_v21_disclaimer = session.pop("show_v21_disclaimer", False)
    return render_template(
        "menu.html",
        modes=AI_MODES,
        show_v21_disclaimer=show_v21_disclaimer,
        **ctx,
    )


@main_bp.route("/select-mode/<mode_key>")
def select_mode(mode_key: str):
    user, err = _require_auth_redirect()
    if err:
        return err
    if mode_key not in AI_MODES:
        flash("Invalid AI mode.", "error")
        return redirect(url_for("main.menu"))

    session["ai_mode"] = mode_key
    settings = db_get_or_create_user_settings(str(user["id"]))
    db_update_user_settings(
        str(user["id"]),
        default_mode=mode_key,
        email_notifications=settings.get("email_notifications", True),
        desktop_notifications=settings.get("desktop_notifications", True),
        auto_title_chats=settings.get("auto_title_chats", True),
        compact_mode=settings.get("compact_mode", False),
    )
    return redirect(url_for("main.index"))


@main_bp.route("/open-chat/<chat_id>")
def open_chat(chat_id: str):
    user, err = _require_auth_redirect()
    if err:
        return err
    chat = db_get_chat(chat_id)
    if not chat or str(chat.get("user_id")) != str(user["id"]):
        flash("Chat not found.", "error")
        return redirect(url_for("main.history_center"))

    session["ai_mode"] = chat.get("mode", "researcher")
    db_restore_chat(chat_id)
    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@main_bp.route("/profile", methods=["GET", "POST"])
def profile():
    user, err = _require_auth_redirect()
    if err:
        return err

    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()
        bio = (request.form.get("bio") or "").strip()
        avatar_color = (request.form.get("avatar_color") or "#7c5cff").strip()[:20]

        if not display_name:
            flash("Display name is required.", "error")
            return redirect(url_for("main.profile"))

        db_update_user_profile(str(user["id"]), display_name, bio[:600], avatar_color)
        session["display_name"] = display_name
        db_create_notification(
            str(user["id"]),
            "Profile updated",
            "Your profile details were successfully updated.",
            "success",
            url_for("main.profile"),
        )
        flash("Profile updated successfully.", "success")
        return redirect(url_for("main.profile"))

    ctx = _dashboard_context(user)
    return render_template("profile.html", **ctx)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@main_bp.route("/settings", methods=["GET", "POST"])
def settings():
    user, err = _require_auth_redirect()
    if err:
        return err

    settings_data = db_get_or_create_user_settings(str(user["id"]))

    if request.method == "POST":
        if request.form.get("form_name") == "password":
            current_password = request.form.get("current_password") or ""
            new_password = request.form.get("new_password") or ""
            confirm_password = request.form.get("confirm_password") or ""

            if not user.get("password_hash"):
                flash("Password changes are unavailable for Google-only accounts until a password is set.", "error")
                return redirect(url_for("main.settings"))
            if not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.", "error")
                return redirect(url_for("main.settings"))
            if len(new_password) < 6:
                flash("New password must be at least 6 characters.", "error")
                return redirect(url_for("main.settings"))
            if new_password != confirm_password:
                flash("New password and confirmation do not match.", "error")
                return redirect(url_for("main.settings"))

            db_update_user_password(str(user["id"]), generate_password_hash(new_password))
            db_create_notification(
                str(user["id"]),
                "Password updated",
                "Your account password was changed successfully.",
                "success",
                url_for("main.settings"),
            )
            flash("Password updated successfully.", "success")
            return redirect(url_for("main.settings"))

        default_mode = request.form.get("default_mode") or "researcher"
        if default_mode not in AI_MODES:
            default_mode = "researcher"

        updated = db_update_user_settings(
            str(user["id"]),
            default_mode=default_mode,
            email_notifications=bool(request.form.get("email_notifications")),
            desktop_notifications=bool(request.form.get("desktop_notifications")),
            auto_title_chats=bool(request.form.get("auto_title_chats")),
            compact_mode=bool(request.form.get("compact_mode")),
        )
        session.setdefault("ai_mode", updated.get("default_mode", default_mode))
        db_create_notification(
            str(user["id"]),
            "Workspace settings saved",
            "Your workspace preferences were updated.",
            "success",
            url_for("main.settings"),
        )
        flash("Workspace settings saved.", "success")
        return redirect(url_for("main.settings"))

    ctx = _dashboard_context(user)
    return render_template("settings.html", settings_data=settings_data, **ctx)


# ---------------------------------------------------------------------------
# Files vault
# ---------------------------------------------------------------------------

@main_bp.route("/files", methods=["GET", "POST"])
def files_page():
    user, err = _require_auth_redirect()
    if err:
        return err

    if request.method == "POST":
        file = request.files.get("file")
        description = (request.form.get("description") or "").strip()
        if not file or not file.filename:
            flash("Choose a file to upload.", "error")
            return redirect(url_for("main.files_page"))

        file_bytes = file.read()
        if len(file_bytes) > MAX_UPLOAD_SIZE:
            flash("File too large. Max upload size is 10 MB.", "error")
            return redirect(url_for("main.files_page"))

        filename = secure_filename(file.filename) or "uploaded-file"
        content_type = file.mimetype or "application/octet-stream"
        db_save_user_file(
            str(user["id"]),
            filename=filename,
            content_type=content_type,
            size_bytes=len(file_bytes),
            description=description[:240],
            file_data=file_bytes,
        )
        db_create_notification(
            str(user["id"]),
            "File uploaded",
            f"{filename} was added to your file vault.",
            "success",
            url_for("main.files_page"),
        )
        flash("File uploaded successfully.", "success")
        return redirect(url_for("main.files_page"))

    ctx = _dashboard_context(user)
    files = db_get_user_files(str(user["id"]))
    total_bytes = sum(int(item.get("size_bytes", 0) or 0) for item in files)
    return render_template("files.html", files=files, total_bytes=total_bytes, **ctx)


@main_bp.route("/files/<file_id>/download")
def download_user_file(file_id: str):
    user, err = _require_auth_redirect()
    if err:
        return err
    item = db_get_user_file(str(user["id"]), file_id)
    if not item:
        flash("File not found.", "error")
        return redirect(url_for("main.files_page"))

    response = make_response(bytes(item["file_data"]))
    response.headers["Content-Type"] = item.get("content_type") or "application/octet-stream"
    response.headers["Content-Disposition"] = f'attachment; filename="{item.get("filename", "download.bin")}"'
    return response


@main_bp.route("/files/<file_id>/delete", methods=["POST"])
def delete_user_file(file_id: str):
    user, err = _require_auth_redirect()
    if err:
        return err
    item = db_get_user_file(str(user["id"]), file_id)
    if item:
        db_delete_user_file(str(user["id"]), file_id)
        db_create_notification(
            str(user["id"]),
            "File removed",
            f"{item.get('filename', 'A file')} was removed from your vault.",
            "info",
            url_for("main.files_page"),
        )
        flash("File deleted.", "success")
    else:
        flash("File not found.", "error")
    return redirect(url_for("main.files_page"))


# ---------------------------------------------------------------------------
# History center
# ---------------------------------------------------------------------------

@main_bp.route("/history-center", methods=["GET", "POST"])
def history_center():
    user, err = _require_auth_redirect()
    if err:
        return err

    if request.method == "POST":
        action = request.form.get("action") or ""
        chat_id = request.form.get("chat_id") or ""
        chat = db_get_chat(chat_id) if chat_id else None
        if not chat or str(chat.get("user_id")) != str(user["id"]):
            flash("Chat not found.", "error")
            return redirect(url_for("main.history_center"))

        if action == "pin":
            db_toggle_pin(chat_id)
            flash("Chat pin updated.", "success")
        elif action == "delete":
            db_delete_chat(chat_id)
            flash("Chat deleted.", "success")
        elif action == "open":
            db_restore_chat(chat_id)
            session["ai_mode"] = chat.get("mode", "researcher")
            return redirect(url_for("main.index"))
        return redirect(url_for("main.history_center"))

    query = (request.args.get("q") or "").strip()
    chats = db_search_chats(str(user["id"]), query) if query else db_get_user_chats(str(user["id"]))
    ctx = _dashboard_context(user)
    return render_template("history.html", chats=chats, search_query=query, **ctx)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@main_bp.route("/notifications", methods=["GET", "POST"])
def notifications_page():
    user, err = _require_auth_redirect()
    if err:
        return err

    if request.method == "POST":
        action = request.form.get("action") or ""
        notification_id = request.form.get("notification_id") or ""
        if action == "read_all":
            db_mark_all_notifications_read(str(user["id"]))
            flash("All notifications marked as read.", "success")
        elif action == "read" and notification_id:
            db_mark_notification_read(str(user["id"]), notification_id)
            flash("Notification marked as read.", "success")
        elif action == "delete" and notification_id:
            db_delete_notification(str(user["id"]), notification_id)
            flash("Notification removed.", "success")
        return redirect(url_for("main.notifications_page"))

    ctx = _dashboard_context(user)
    notifications = db_get_user_notifications(str(user["id"]), limit=100)
    return render_template("notifications.html", notifications=notifications, **ctx)
