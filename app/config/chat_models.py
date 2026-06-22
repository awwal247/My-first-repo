"""
app/config/chat_models.py
=========================
Workspace-selectable chat model presets for Zenith OX v2.5.

These presets let the user choose a model from the chat UI without
changing the higher-level AI mode (Developer, Researcher, Story Writer,
etc.). Each preset can override the OpenRouter primary model and, when
appropriate, the Groq fallback model.
"""

from __future__ import annotations

AVAILABLE_CHAT_MODELS: dict[str, dict[str, str]] = {
    "llama_versatile_31": {
        "label": "Meta Llama Versatile 3.1",
        "provider": "Meta",
        "description": "Balanced for coding and general tasks",
        "openrouter_model": "meta-llama/llama-3.1-70b-instruct",
        # Groq no longer exposes a matching 3.1 versatile flagship; use the
        # closest maintained fallback when OpenRouter is unavailable.
        "groq_model": "llama-3.3-70b-versatile",
    },
    "gpt_oss_120b": {
        "label": "OpenAI GPT OSS 120B",
        "provider": "OpenAI",
        "description": "Strong reasoning and long-form generation",
        "openrouter_model": "openai/gpt-oss-120b:free",
        "groq_model": "llama-3.3-70b-versatile",
    },
    "gemini_flash_31": {
        "label": "Google Gemini Flash 3.1",
        "provider": "Google",
        "description": "Fast, responsive everyday workspace model",
        # Current stable OpenRouter model family used for the Flash preset.
        "openrouter_model": "google/gemini-2.5-flash",
        "groq_model": "llama-3.3-70b-versatile",
    },
    "gemini_pro": {
        "label": "Google Gemini Pro",
        "provider": "Google",
        "description": "Higher-depth reasoning and complex tasks",
        "openrouter_model": "google/gemini-2.5-pro",
        "groq_model": "llama-3.3-70b-versatile",
    },
}

DEFAULT_CHAT_MODEL_KEY = "llama_versatile_31"


def get_chat_models_for_ui() -> dict[str, dict[str, str]]:
    """Return the model catalog without internal-only keys."""
    return {
        key: {
            "label": value["label"],
            "provider": value["provider"],
            "description": value["description"],
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
