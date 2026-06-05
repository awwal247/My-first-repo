"""
api/index.py
============
Vercel serverless entry-point.

Vercel expects a WSGI-compatible ``app`` object in this file.
We simply delegate to the application factory so there is
**zero** business logic here — the full application lives
inside the ``app/`` package.
"""

import sys
import os

# Make the project root importable when running under Vercel
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402

app = create_app()

# Required by Vercel's Python runtime
application = app
