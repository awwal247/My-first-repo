"""
app/config/settings.py
======================
Centralised configuration. All environment variables and
application-level constants live here — nowhere else.

v4.0 changes:
  - Added HF_TOKEN for HuggingFace Inference API
  - Added POLLINATIONS_BASE for PPTX image generation
"""

import os
import secrets

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration loaded from environment variables."""

    # Flask
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # AI / Groq (fallback)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # HuggingFace (primary — v4.0)
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")
    HF_API_URL: str = "https://api-inference.huggingface.co/models"
    # Default inference parameters
    HF_MAX_RETRIES: int = 3
    HF_TIMEOUT: int = 30  # seconds

    # Pollinations.ai — free image generation for PPTX slides
    POLLINATIONS_BASE: str = "https://image.pollinations.ai/prompt"

    # Web search
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # Database (Supabase / PostgreSQL)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Storage (legacy paths — kept for local dev reference only)
    BASE_DIR: str = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    USERS_FILE: str = os.path.join(BASE_DIR, "users.json")
    MEMORY_FILE: str = os.path.join(BASE_DIR, "memory.json")
    WRITABLE_USERS: str = "/tmp/users.json"
    WRITABLE_MEMORY: str = "/tmp/memory.json"

    # Memory limits
    MEMORY_LIMIT: int = 15
    TOP_K_MEMORY: int = 3

    # Upload limits
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB
