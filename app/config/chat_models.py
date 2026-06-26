"""
app/config/chat_models.py
=========================
Workspace-selectable chat model presets for Zenith OX v2.7.

These presets let the user choose a model from the chat UI without
changing the higher-level AI mode (Developer, Researcher, Story Writer,
etc.). Each preset can override the OpenRouter primary model and, when
appropriate, the Groq fallback model.

v2.7 — Added `premium_only` flag.  Gemini models require Pro/Premium.
"""

from __future__ import annotations

AVAILABLE_CHAT_MODELS: dict[str, dict] = {
    "llama_versatile_31": {
        "label": "Meta Llama Versatile 3.1",
        "provider": "Meta",
        "description": "Balanced for coding and general tasks",
        "openrouter_model": "meta-llama/llama-3.1-70b-instruct",
        # Groq no longer exposes a matching 3.1 versatile flagship; use the
        # closest maintained fallback when OpenRouter is unavailable.
        "groq_model": "llama-3.3-70b-versatile",
        "premium_only": False,
    },
    "gpt_oss_120b": {
        "label": "OpenAI GPT OSS 120B",
        "provider": "OpenAI",
        "description": "Strong reasoning and long-form generation",
        "openrouter_model": "openai/gpt-oss-120b:free",
        "groq_model": "llama-3.3-70b-versatile",
        "premium_only": False,
    },
    "gemini_flash_31": {
        "label": "Google Gemini Flash 1.5",
        "provider": "Google",
        "description": "Fast, responsive everyday workspace model — Pro/Premium only",
        "openrouter_model": "google/gemini-flash-1.5",
        "groq_model": "llama-3.3-70b-versatile",
        "premium_only": True,   # Free users cannot use this model
    },
    "gemini_pro": {
        "label": "Google Gemini Pro 1.5",
        "provider": "Google",
        "description": "Higher-depth reasoning and complex tasks — Pro/Premium only",
        "openrouter_model": "google/gemini-pro-1.5",
        "groq_model": "llama-3.3-70b-versatile",
        "premium_only": True,   # Free users cannot use this model
    },
}

DEFAULT_CHAT_MODEL_KEY = "llama_versatile_31"


def get_chat_models_for_ui(is_premium: bool = False) -> dict[str, dict]:
    """
    Return the model catalog for the UI.

    All models are listed (so the user can see them), but premium-only
    models are tagged so the frontend can disable/lock them for free users.
    """
    return {
        key: {
            "label": value["label"],
            "provider": value["provider"],
            "description": value["description"],
            "premium_only": value.get("premium_only", False),
        }
        for key, value in AVAILABLE_CHAT_MODELS.items()
    }


def apply_chat_model_override(mode: dict, model_key: str | None) -> dict:
    """Return a copy of `mode` with the selected workspace model applied."""
    merged = dict(mode)
    preset = AVAILABLE_CHAT_MODELS.get(model_key or "")
    if not preset:
        return merged

    merged["openrouter_model"] = preset["openrouter_model"]
    merged["model"] = preset["groq_model"]
    merged["selected_chat_model_key"] = model_key
    merged["selected_chat_model_label"] = preset["label"]
    return merged


def is_model_premium_only(model_key: str) -> bool:
    """Return True if the given model key requires Pro/Premium."""
    return AVAILABLE_CHAT_MODELS.get(model_key, {}).get("premium_only", False)
