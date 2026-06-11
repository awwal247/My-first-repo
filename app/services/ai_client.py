"""
app/services/ai_client.py
=========================
Unified AI client with HuggingFace-first routing and Groq fallback.

v4.0 architecture:
  1. ask_ai() — main entry point; tries HF first, falls back to Groq
  2. ask_hf() — HuggingFace Inference API (primary)
  3. ask_groq() — Groq API (fallback when HF fails / unavailable)
  4. ask_groq_vision() — Groq multimodal for image analysis

Usage:
  from app.services.ai_client import ask_ai
  answer = ask_ai(message, vector_memory, web_context, mode_config)
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import requests

from app.config.settings import Config

_cfg = Config()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hf_headers() -> dict[str, str]:
    """Return authorization headers for HuggingFace Inference API."""
    return {"Authorization": f"Bearer {_cfg.HF_TOKEN}", "Content-Type": "application/json"}

def _groq_headers() -> dict[str, str]:
    """Return authorization headers for Groq API."""
    return {"Authorization": f"Bearer {_cfg.GROQ_API_KEY}", "Content-Type": "application/json"}

def _build_messages(
    user_message: str,
    mode: dict,
    vector_memory: str = "",
    web_context: str = "",
    recent_history: list | None = None,
) -> list[dict[str, str]]:
    """Build the OpenAI-compatible messages list for both HF and Groq."""
    sys_parts = [mode.get("system_prompt", "You are a helpful assistant.")]
    if vector_memory:
        sys_parts.append(f"\n\nRelevant past memory:\n{vector_memory}")
    if web_context:
        sys_parts.append(f"\n\nWeb search results:\n{web_context}")

    messages: list[dict[str, str]] = [
        {"role": "system", "content": "\n".join(sys_parts)},
    ]

    # Inject recent history (last N exchanges)
    if recent_history:
        for h in recent_history[-10:]:
            messages.append({"role": h["role"], "content": h["content"]})

    messages.append({"role": "user", "content": user_message})
    return messages

# ---------------------------------------------------------------------------
# HuggingFace Inference API (PRIMARY)
# ---------------------------------------------------------------------------

def ask_hf(
    user_message: str,
    mode: dict,
    vector_memory: str = "",
    web_context: str = "",
    recent_history: list | None = None,
) -> str:
    """
    Call HuggingFace Inference API.

    Uses the mode-specific hf_model if configured, otherwise falls
    back to a general-purpose model.

    Raises RuntimeError on failure so the caller can retry with Groq.
    """
    hf_model = mode.get("hf_model", "meta-llama/Llama-2-70b-chat-hf")
    url = f"{_cfg.HF_API_URL}/{hf_model}"

    messages = _build_messages(user_message, mode, vector_memory, web_context, recent_history)

    payload: dict[str, Any] = {
        "inputs": _format_hf_chat(messages),
        "parameters": {
            "temperature": mode.get("temperature", 0.7),
            "max_new_tokens": mode.get("max_tokens", 2000),
            "return_full_text": False,
            "do_sample": True,
        },
        "options": {"wait_for_model": True, "use_cache": True},
    }

    last_err: Exception | None = None
    for attempt in range(1, _cfg.HF_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                headers=_hf_headers(),
                json=payload,
                timeout=_cfg.HF_TIMEOUT,
            )
            # HF sometimes returns 503 while loading — retry
            if resp.status_code in (503, 504):
                time.sleep(2 * attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            # HF inference format: [{"generated_text": "..."}]
            if isinstance(data, list) and data:
                generated = data[0].get("generated_text", "")
                # Strip the echo'd prompt if present
                prompt_text = messages[-1]["content"]
                if generated.startswith(prompt_text):
                    generated = generated[len(prompt_text):].strip()
                return generated or data[0].get("text", "")
            elif isinstance(data, dict):
                return data.get("generated_text", data.get("text", ""))
            return str(data)
        except requests.exceptions.Timeout:
            last_err = RuntimeError(f"HF timeout (attempt {attempt})")
            time.sleep(1)
        except requests.exceptions.HTTPError as exc:
            last_err = RuntimeError(f"HF HTTP error: {exc.response.status_code} — {exc.response.text[:200]}")
            if exc.response.status_code in (503, 504, 429):
                time.sleep(2 * attempt)
                continue
            raise last_err
        except Exception as exc:
            last_err = RuntimeError(f"HF error: {exc}")
            time.sleep(1)

    raise last_err or RuntimeError("HF inference failed after all retries")

def _format_hf_chat(messages: list[dict[str, str]]) -> str:
    """
    Convert OpenAI-style messages to a prompt string for HF chat models.
    Uses Llama-2 chat format by default.
    """
    parts: list[str] = []
    for m in messages:
        role = m["role"]
        content = m["content"]
        if role == "system":
            parts.append(f"[INST] <<SYS>>\n{content}\n<</SYS>>\n\n")
        elif role == "user":
            parts.append(f"{content} [/INST]")
        elif role == "assistant":
            parts.append(f" {content} </s><s>[INST]")
    return "".join(parts)

# ---------------------------------------------------------------------------
# Groq API (FALLBACK)
# ---------------------------------------------------------------------------

def ask_groq(
    user_message: str,
    vector_memory: str = "",
    web_context: str = "",
    mode: dict | None = None,
    recent_history: list | None = None,
) -> str:
    """
    Call Groq API. This is the **fallback** when HF is unavailable.

    Parameters
    ----------
    user_message : The user's current message.
    vector_memory : Relevant past memory (string).
    web_context : Web search results (string).
    mode : AI mode dict from AI_MODES.
    recent_history : List of {"role": ..., "content": ...} dicts.

    Returns
    -------
    str — the assistant's reply.
    """
    mode = mode or {}
    model = mode.get("model", "llama-3.3-70b-versatile")
    messages = _build_messages(user_message, mode, vector_memory, web_context, recent_history)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": mode.get("temperature", 0.7),
        "max_tokens": mode.get("max_tokens", 2000),
    }

    resp = requests.post(
        f"{_cfg.GROQ_BASE_URL}/chat/completions",
        headers=_groq_headers(),
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]

def ask_groq_vision(
    message: str,
    b64_image: str,
    media_type: str = "image/jpeg",
    meta: str = "",
    mode: dict | None = None,
    recent_history: list | None = None,
) -> str:
    """
    Call Groq Vision (Llama 4 Scout multimodal) for image analysis.

    Parameters
    ----------
    message : User's question about the image.
    b64_image : Base64-encoded image data (no data-url prefix).
    media_type : MIME type of the image.
    meta : Optional metadata string (shown in system prompt).
    mode : AI mode dict.
    recent_history : Recent conversation history.

    Returns
    -------
    str — the assistant's description / analysis.
    """
    mode = mode or {}
    sys_text = mode.get("system_prompt", "You are a helpful assistant.")
    if meta:
        sys_text += f"\n\nImage metadata: {meta}"

    content: list[dict[str, Any]] = [
        {"type": "text", "text": message},
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{media_type};base64,{b64_image}",
                "detail": "auto",
            },
        },
    ]

    messages: list[dict[str, Any]] = [{"role": "system", "content": sys_text}]
    if recent_history:
        for h in recent_history[-6:]:
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": content})

    payload = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 2000,
    }

    resp = requests.post(
        f"{_cfg.GROQ_BASE_URL}/chat/completions",
        headers=_groq_headers(),
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]

# ---------------------------------------------------------------------------
# Unified entry point — HF first, Groq fallback
# ---------------------------------------------------------------------------

def ask_ai(
    user_message: str,
    vector_memory: str = "",
    web_context: str = "",
    mode: dict | None = None,
    recent_history: list | None = None,
) -> str:
    """
    Unified AI call. Tries HuggingFace first; falls back to Groq on failure.

    Parameters match ask_groq / ask_hf exactly.

    Returns
    -------
    str — the assistant's reply.
    """
    mode = mode or {}

    # If no HF token is configured, skip directly to Groq
    if not _cfg.HF_TOKEN:
        return ask_groq(user_message, vector_memory, web_context, mode, recent_history)

    # Try HuggingFace first
    try:
        return ask_hf(user_message, mode, vector_memory, web_context, recent_history)
    except Exception as exc:
        # Log the HF failure and fall back to Groq
        import logging
        _log = logging.getLogger(__name__)
        _log.warning("HF inference failed, falling back to Groq: %s", exc)
        return ask_groq(user_message, vector_memory, web_context, mode, recent_history)

# Keep ask_groq available as a direct import for backward compatibility
__all__ = ["ask_ai", "ask_hf", "ask_groq", "ask_groq_vision"]
