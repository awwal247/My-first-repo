"""Authentication routes for Zenith OX — v2.7.

Changes vs v2.6:
  - send_login_notification() called after every successful sign-in
    (email/password login, Google OAuth, new Google account creation).
"""

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.services.db import (
    db_create_notification,
    db_create_user,
    db_find_user_by_email,
    db_find_user_by_google_id,
    db_link_google_id,
    ensure_runtime_schema,
)
from app.utils.auth import display_name_from_email, valid_email

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _send_login_notification(user_id: str) -> None:
    """
    Fire a login-security notification immediately after a successful sign-in.
    Delegates to python_additions.login_notify so all detection logic lives there.
    Fails silently — a notification error must never break the login flow.
    """
    try:
        from python_additions.login_notify import send_login_notification
        from app.services.db import get_supabase_client  # adjust if your project exposes supabase differently
        sb = get_supabase_client()
        send_login_notification(sb, user_id=user_id)
    except Exception as exc:
        current_app.logger.warning("[auth] Login notification failed: %s", exc)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm") or ""
    name = (request.form.get("name") or "").strip()

    if not name:
        flash("Display name is required.", "error")
        return redirect(url_for("auth.register"))
    if not valid_email(email):
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("auth.register"))
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("auth.register"))
    if password != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for("auth.register"))

    try:
        ensure_runtime_schema()
        existing = db_find_user_by_email(email)
    except RuntimeError as exc:
        flash(f"Database error: {exc}", "error")
        return redirect(url_for("auth.register"))

    if existing:
        flash("An account with that email already exists. Please log in.", "error")
        return redirect(url_for("auth.login_page"))

    try:
        user = db_create_user(
            email=email,
            display_name=name,
            password_hash=generate_password_hash(password),
            google_id=None,
        )
        db_create_notification(
            str(user["id"]),
            "Welcome to Zenith OX",
            "Your workspace is ready. Explore the dashboard, chat modes, files vault, and settings center.",
            "success",
            url_for("main.menu"),
        )
    except RuntimeError as exc:
        flash(f"Could not create account: {exc}", "error")
        return redirect(url_for("auth.register"))

    session["user_id"] = str(user["id"])
    session["display_name"] = user["display_name"]
    session["show_v21_disclaimer"] = True
    flash("Account created. Welcome!", "success")
    return redirect(url_for("main.menu"))


# ---------------------------------------------------------------------------
# Login (email / password)
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        return render_template("login.html")

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    if not valid_email(email) or not password:
        flash("Please enter your email and password.", "error")
        return redirect(url_for("auth.login_page"))

    try:
        user = db_find_user_by_email(email)
    except RuntimeError as exc:
        flash(f"Database error: {exc}", "error")
        return redirect(url_for("auth.login_page"))

    if not user or not user.get("password_hash"):
        flash("No account found with that email, or it was created via Google.", "error")
        return redirect(url_for("auth.login_page"))
    if not check_password_hash(user["password_hash"], password):
        flash("Incorrect password.", "error")
        return redirect(url_for("auth.login_page"))

    session["user_id"] = str(user["id"])
    session["display_name"] = user.get("display_name") or display_name_from_email(email)
    session["show_v21_disclaimer"] = True

    # v2.7 — Security notification on every login
    _send_login_notification(str(user["id"]))

    return redirect(url_for("main.menu"))


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

@auth_bp.route("/login/google")
def login_google():
    google = current_app.extensions.get("google_oauth")
    if not google:
        flash("Google login is not configured.", "error")
        return redirect(url_for("auth.login_page"))
    return google.authorize_redirect(url_for("auth.auth_google_callback", _external=True))


@auth_bp.route("/auth/google/callback")
def auth_google_callback():
    google = current_app.extensions.get("google_oauth")
    if not google:
        flash("Google login is not configured.", "error")
        return redirect(url_for("auth.login_page"))
    try:
        token = google.authorize_access_token()
    except Exception as exc:
        flash(f"Google sign-in failed: {exc}", "error")
        return redirect(url_for("auth.login_page"))

    userinfo = token.get("userinfo") or {}
    google_id = userinfo.get("sub")
    email = (userinfo.get("email") or "").strip().lower()
    name = userinfo.get("name") or display_name_from_email(email)
    if not google_id or not email:
        flash("Google did not return required profile info.", "error")
        return redirect(url_for("auth.login_page"))

    try:
        google_user = db_find_user_by_google_id(google_id)
        if google_user:
            session["user_id"] = str(google_user["id"])
            session["display_name"] = google_user.get("display_name") or display_name_from_email(email)
            session["show_v21_disclaimer"] = True
            # v2.7 — Security notification on every login
            _send_login_notification(str(google_user["id"]))
            return redirect(url_for("main.menu"))

        email_user = db_find_user_by_email(email)
        if email_user:
            db_link_google_id(str(email_user["id"]), google_id)
            session["user_id"] = str(email_user["id"])
            session["display_name"] = email_user.get("display_name") or display_name_from_email(email)
            session["show_v21_disclaimer"] = True
            # v2.7 — Security notification on every login
            _send_login_notification(str(email_user["id"]))
            return redirect(url_for("main.menu"))

        new_user = db_create_user(email=email, display_name=name, password_hash=None, google_id=google_id)
        db_create_notification(
            str(new_user["id"]),
            "Welcome to Zenith OX",
            "Your Google account is linked and your workspace is ready.",
            "success",
            url_for("main.menu"),
        )
        session["user_id"] = str(new_user["id"])
        session["display_name"] = new_user["display_name"]
        session["show_v21_disclaimer"] = True
        # v2.7 — Security notification on first Google sign-in too
        _send_login_notification(str(new_user["id"]))
        return redirect(url_for("main.menu"))

    except RuntimeError as exc:
        flash(f"Database error during Google sign-in: {exc}", "error")
        return redirect(url_for("auth.login_page"))


# ---------------------------------------------------------------------------
# Logout / delete
# ---------------------------------------------------------------------------

@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login_page"))


@auth_bp.route("/delete-account", methods=["POST"])
def delete_account():
    """Permanently delete the logged-in user and all data."""
    if "user_id" not in session:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    data = request.get_json(silent=True) or {}
    if data.get("confirm") != "DELETE":
        return jsonify({"ok": False, "error": "Type DELETE to confirm"}), 400

    user_id = session["user_id"]
    try:
        from app.services.db import close_connection, get_connection

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
        finally:
            close_connection(conn)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    session.clear()
    return jsonify({"ok": True})
