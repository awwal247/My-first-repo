"""
ZENITH OX v2.7 — Create Default Test User
==========================================
Run this script ONCE to create the default premium test account.
It gives full Pro/Premium access so you can test all v2.7 features.

CREDENTIALS:
    Username: Zenith
    Email:    ZenithoxPro@gmail.com
    Password: ZenithoxSecret

RUN:
    python create_test_user.py

Or call create_default_test_user() from your app factory / CLI command.

IMPORTANT: Only run this in development. The account is for testing only.
"""

import os
import sys

# ─── Adjust this import to match your project structure ──────────────────────
# from your_app import create_app, db
# from your_app.models import User
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_TEST_USER = {
    "username": "Zenith",
    "email": "ZenithoxPro@gmail.com",
    "password": "ZenithoxSecret",
    "is_premium": True,       # Full Pro/Premium access
    "is_admin": True,         # Admin access for testing
    "avatar_color": "#7c5cff",
}


def create_default_test_user(supabase=None, User=None, db=None):
    """
    Create the default Zenith test user if it doesn't already exist.

    Depending on your auth setup, choose ONE of the approaches below:

    ── APPROACH A: Supabase Auth (if you use supabase.auth) ────────────────
    """
    if supabase:
        try:
            # Check if user already exists
            existing = (
                supabase.table("users")
                .select("id")
                .eq("email", DEFAULT_TEST_USER["email"])
                .execute()
            )
            if existing.data:
                print(f"[TestUser] User {DEFAULT_TEST_USER['email']} already exists.")
                return

            # Create via Supabase Auth
            auth_result = supabase.auth.sign_up({
                "email": DEFAULT_TEST_USER["email"],
                "password": DEFAULT_TEST_USER["password"],
            })

            if auth_result.user:
                user_id = auth_result.user.id
                # Upsert profile row
                supabase.table("users").upsert({
                    "id": user_id,
                    "username": DEFAULT_TEST_USER["username"],
                    "email": DEFAULT_TEST_USER["email"],
                    "is_premium": DEFAULT_TEST_USER["is_premium"],
                    "is_admin": DEFAULT_TEST_USER["is_admin"],
                    "avatar_color": DEFAULT_TEST_USER["avatar_color"],
                }).execute()
                print(f"[TestUser] ✓ Created test user: {DEFAULT_TEST_USER['email']}")
            else:
                print(f"[TestUser] ✗ Failed to create user via Supabase Auth.")

        except Exception as e:
            print(f"[TestUser] Error: {e}")
        return

    # ── APPROACH B: Flask-SQLAlchemy + Werkzeug ──────────────────────────────
    if User and db:
        try:
            from werkzeug.security import generate_password_hash
            existing = User.query.filter_by(email=DEFAULT_TEST_USER["email"]).first()
            if existing:
                print(f"[TestUser] User {DEFAULT_TEST_USER['email']} already exists.")
                return

            user = User(
                username=DEFAULT_TEST_USER["username"],
                email=DEFAULT_TEST_USER["email"],
                password_hash=generate_password_hash(DEFAULT_TEST_USER["password"]),
                is_premium=DEFAULT_TEST_USER["is_premium"],
                is_admin=DEFAULT_TEST_USER["is_admin"],
                avatar_color=DEFAULT_TEST_USER["avatar_color"],
            )
            db.session.add(user)
            db.session.commit()
            print(f"[TestUser] ✓ Created test user: {DEFAULT_TEST_USER['email']}")

        except Exception as e:
            print(f"[TestUser] Error: {e}")
        return

    print("[TestUser] No supabase client or ORM model provided. Pass one to create the user.")


# ── Call from your Flask CLI ──────────────────────────────────────────────────
"""
Add to your Flask app (app.py or __init__.py):

    @app.cli.command("create-test-user")
    def create_test_user_command():
        from python_additions.create_test_user import create_default_test_user
        create_default_test_user(supabase=supabase)  # or pass db, User

Then run: flask create-test-user
"""

if __name__ == "__main__":
    print("Run via Flask CLI: flask create-test-user")
    print(f"Target credentials: {DEFAULT_TEST_USER['email']} / {DEFAULT_TEST_USER['password']}")
