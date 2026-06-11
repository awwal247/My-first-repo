"""
app.py
======
Application entry point for **local development**.

Usage
-----
 python app.py
 # or via Flask CLI:
 flask run

For production deployments (e.g. Vercel) the WSGI adapter
lives in ``api/index.py``.
"""

from app import create_app

flask_app = create_app()

# Expose ``application`` for any WSGI server that looks for it by name
application = flask_app

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=5000, debug=flask_app.config.get("DEBUG", False))
