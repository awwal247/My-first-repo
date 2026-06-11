"""
ZenithOX v4.0 — Application Package
=====================================
Flask application factory and package initialiser.

v4.0 changes:
  - Registered chats_bp blueprint for chat session management
  - Added HF_TOKEN config integration
"""

from flask import Flask
from authlib.integrations.flask_client import OAuth

from app.config.settings import Config

oauth = OAuth()


def create_app(config: Config | None = None) -> Flask:
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )

    cfg = config or Config()
    app.secret_key = cfg.SECRET_KEY
    app.config.from_object(cfg)

    oauth.init_app(app)

    google = None
    if cfg.GOOGLE_CLIENT_ID and cfg.GOOGLE_CLIENT_SECRET:
        google = oauth.register(
            name="google",
            client_id=cfg.GOOGLE_CLIENT_ID,
            client_secret=cfg.GOOGLE_CLIENT_SECRET,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    app.jinja_env.globals["google_enabled"] = lambda: google is not None

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.chat import chat_bp
    from app.routes.chats import chats_bp
    from app.routes.main import main_bp
    from app.routes.landing import landing_bp

    app.register_blueprint(landing_bp)  # handles / (public)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(chats_bp)  # v4.0 — chat session management
    app.register_blueprint(main_bp)

    app.extensions["google_oauth"] = google

    return app
