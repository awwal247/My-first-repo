"""
ZenithOX — Application Package
==============================
Flask application factory and package initialiser.
"""

from authlib.integrations.flask_client import OAuth
from flask import Flask

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

    try:
        from app.services.db import ensure_runtime_schema

        ensure_runtime_schema()
    except Exception as exc:  # pragma: no cover - app can still boot for static pages
        print(f"[zenith] schema bootstrap skipped: {exc}")

    from app.routes.auth import auth_bp
    from app.routes.chat import chat_bp
    from app.routes.chats import chats_bp
    from app.routes.landing import landing_bp
    from app.routes.main import main_bp

    app.register_blueprint(landing_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(chats_bp)
    app.register_blueprint(main_bp)

    app.extensions["google_oauth"] = google
    return app
