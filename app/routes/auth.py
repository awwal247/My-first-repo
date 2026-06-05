"""app/routes/auth.py -- display name required; /delete-account endpoint."""
from flask import Blueprint,current_app,flash,jsonify,redirect,render_template,request,session,url_for
from werkzeug.security import check_password_hash,generate_password_hash
from app.services.db import db_create_user,db_find_user_by_email,db_find_user_by_google_id,db_link_google_id
from app.utils.auth import display_name_from_email,valid_email

auth_bp = Blueprint("auth",__name__)

@auth_bp.route("/register",methods=["GET","POST"])
def register():
    if request.method=="GET": return render_template("register.html")
    email=(request.form.get("email") or "").strip().lower()
    password=request.form.get("password") or ""; confirm=request.form.get("confirm") or ""
    name=(request.form.get("name") or "").strip()
    if not name:
        flash("Display name is required.","error"); return redirect(url_for("auth.register"))
    if not valid_email(email):
        flash("Please enter a valid email address.","error"); return redirect(url_for("auth.register"))
    if len(password)<6:
        flash("Password must be at least 6 characters.","error"); return redirect(url_for("auth.register"))
    if password!=confirm:
        flash("Passwords do not match.","error"); return redirect(url_for("auth.register"))
    try: existing=db_find_user_by_email(email)
    except RuntimeError as exc:
        flash(f"Database error: {exc}","error"); return redirect(url_for("auth.register"))
    if existing:
        flash("An account with that email already exists. Please log in.","error")
        return redirect(url_for("auth.login_page"))
    try:
        user=db_create_user(email=email,display_name=name,
                            password_hash=generate_password_hash(password),google_id=None)
    except RuntimeError as exc:
        flash(f"Could not create account: {exc}","error"); return redirect(url_for("auth.register"))
    session["user_id"]=str(user["id"]); session["display_name"]=user["display_name"]
    flash("Account created. Welcome!","success"); return redirect(url_for("main.menu"))

@auth_bp.route("/login",methods=["GET","POST"])
def login_page():
    if request.method=="GET": return render_template("login.html")
    email=(request.form.get("email") or "").strip().lower()
    password=request.form.get("password") or ""
    if not valid_email(email) or not password:
        flash("Please enter your email and password.","error"); return redirect(url_for("auth.login_page"))
    try: user=db_find_user_by_email(email)
    except RuntimeError as exc:
        flash(f"Database error: {exc}","error"); return redirect(url_for("auth.login_page"))
    if not user or not user.get("password_hash"):
        flash("No account found with that email, or it was created via Google.","error")
        return redirect(url_for("auth.login_page"))
    if not check_password_hash(user["password_hash"],password):
        flash("Incorrect password.","error"); return redirect(url_for("auth.login_page"))
    session["user_id"]=str(user["id"])
    session["display_name"]=user.get("display_name") or display_name_from_email(email)
    return redirect(url_for("main.menu"))

@auth_bp.route("/login/google")
def login_google():
    g=current_app.extensions.get("google_oauth")
    if not g: flash("Google login is not configured.","error"); return redirect(url_for("auth.login_page"))
    return g.authorize_redirect(url_for("auth.auth_google_callback",_external=True))

@auth_bp.route("/auth/google/callback")
def auth_google_callback():
    g=current_app.extensions.get("google_oauth")
    if not g: flash("Google login is not configured.","error"); return redirect(url_for("auth.login_page"))
    try: token=g.authorize_access_token()
    except Exception as exc:
        flash(f"Google sign-in failed: {exc}","error"); return redirect(url_for("auth.login_page"))
    ui=token.get("userinfo") or {}
    gid=ui.get("sub"); em=(ui.get("email") or "").strip().lower()
    nm=ui.get("name") or display_name_from_email(em)
    if not gid or not em:
        flash("Google did not return required profile info.","error"); return redirect(url_for("auth.login_page"))
    try:
        gu=db_find_user_by_google_id(gid)
        if gu:
            session["user_id"]=str(gu["id"])
            session["display_name"]=gu.get("display_name") or display_name_from_email(em)
            return redirect(url_for("main.menu"))
        eu=db_find_user_by_email(em)
        if eu:
            db_link_google_id(str(eu["id"]),gid)
            session["user_id"]=str(eu["id"])
            session["display_name"]=eu.get("display_name") or display_name_from_email(em)
            return redirect(url_for("main.menu"))
        nu=db_create_user(email=em,display_name=nm,password_hash=None,google_id=gid)
        session["user_id"]=str(nu["id"]); session["display_name"]=nu["display_name"]
        return redirect(url_for("main.menu"))
    except RuntimeError as exc:
        flash(f"Database error during Google sign-in: {exc}","error")
        return redirect(url_for("auth.login_page"))

@auth_bp.route("/logout",methods=["GET","POST"])
def logout():
    session.clear(); return redirect(url_for("auth.login_page"))

@auth_bp.route("/delete-account",methods=["POST"])
def delete_account():
    """Permanently delete the logged-in user and ALL their data (CASCADE removes chats/conversations)."""
    if "user_id" not in session:
        return jsonify({"ok":False,"error":"Not authenticated"}),401
    data=request.get_json(silent=True) or {}
    if data.get("confirm")!="DELETE":
        return jsonify({"ok":False,"error":"Type DELETE to confirm"}),400
    uid=session["user_id"]
    try:
        from app.services.db import get_connection,close_connection
        conn=get_connection()
        try:
            with conn.cursor() as cur: cur.execute("DELETE FROM users WHERE id=%s",(uid,))
            conn.commit()
        finally: close_connection(conn)
    except Exception as exc:
        return jsonify({"ok":False,"error":str(exc)}),500
    session.clear()
    return jsonify({"ok":True})
