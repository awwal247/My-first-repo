"""
app/services/ai_client.py
=========================
Unified AI client with OpenRouter-first routing and Groq fallback.

OpenRouter version architecture:
  1. ask_ai() — main entry point; tries OpenRouter first, falls back to Groq
  2. ask_openrouter() — OpenRouter API (primary)
  3. ask_groq() — Groq API (fallback when OpenRouter fails / unavailable)
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

def _or_headers() -> dict[str, str]:
    """Return authorization headers for OpenRouter API."""
    return {
        "Authorization": f"Bearer {_cfg.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://zenith-ox.vercel.app",  # Required by OpenRouter
        "X-Title": "Zenith OX",
    }

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
    """Build the OpenAI-compatible messages list for both OpenRouter and Groq."""
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
# OpenRouter API (PRIMARY)
# ---------------------------------------------------------------------------

def ask_openrouter(
    user_message: str,
    mode: dict,
    vector_memory: str = "",
    web_context: str = "",
    recent_history: list | None = None,
) -> str:
    """
    Call OpenRouter API (OpenAI-compatible).

    Uses the mode-specific openrouter_model if configured, otherwise falls
    back to a general-purpose model.

    Raises RuntimeError on failure so the caller can retry with Groq.
    """
    or_model = mode.get("openrouter_model", "meta-llama/llama-3.3-70b-instruct:free")
    url = f"{_cfg.OPENROUTER_BASE_URL}/chat/completions"

    messages = _build_messages(user_message, mode, vector_memory, web_context, recent_history)

    payload: dict[str, Any] = {
        "model": or_model,
        "messages": messages,
        "temperature": mode.get("temperature", 0.7),
        "max_tokens": mode.get("max_tokens", 2000),
    }

    try:
        resp = requests.post(
            url,
            headers=_or_headers(),
            json=payload,
            timeout=_cfg.OPENROUTER_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        raise RuntimeError("OpenRouter timeout")
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(f"OpenRouter HTTP error: {exc.response.status_code} — {exc.response.text[:200]}")
    except Exception as exc:
        raise RuntimeError(f"OpenRouter error: {exc}")


def ask_openrouter_stream(
    user_message: str,
    mode: dict,
    vector_memory: str = "",
    web_context: str = "",
    recent_history: list | None = None,
):
    """
    Call OpenRouter API with `stream: true` and yield text deltas as they
    arrive (v2.1 "AI text tracker").

    Raises RuntimeError if the connection/request itself fails. If the
    request succeeds but the model returns nothing, yields nothing
    (caller decides how to handle an empty stream).
    """
    or_model = mode.get("openrouter_model", "meta-llama/llama-3.3-70b-instruct:free")
    url = f"{_cfg.OPENROUTER_BASE_URL}/chat/completions"

    messages = _build_messages(user_message, mode, vector_memory, web_context, recent_history)

    payload: dict[str, Any] = {
        "model": or_model,
        "messages": messages,
        "temperature": mode.get("temperature", 0.7),
        "max_tokens": mode.get("max_tokens", 2000),
        "stream": True,
    }

    try:
        resp = requests.post(
            url,
            headers=_or_headers(),
            json=payload,
            timeout=_cfg.OPENROUTER_TIMEOUT,
            stream=True,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError("OpenRouter timeout")
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(f"OpenRouter HTTP error: {exc.response.status_code} — {exc.response.text[:200]}")
    except Exception as exc:
        raise RuntimeError(f"OpenRouter error: {exc}")

    for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        if not raw_line.startswith("data:"):
            continue
        data_str = raw_line[len("data:"):].strip()
        if data_str == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
        except Exception:
            continue
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if content:
            yield content

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
    Call Groq API. This is the **fallback** when OpenRouter is unavailable.

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


def ask_groq_stream(
    user_message: str,
    vector_memory: str = "",
    web_context: str = "",
    mode: dict | None = None,
    recent_history: list | None = None,
):
    """
    Call Groq API with `stream: true` and yield text deltas as they arrive.
    Used as the streaming fallback when OpenRouter streaming is unavailable.
    """
    mode = mode or {}
    model = mode.get("model", "llama-3.3-70b-versatile")
    messages = _build_messages(user_message, mode, vector_memory, web_context, recent_history)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": mode.get("temperature", 0.7),
        "max_tokens": mode.get("max_tokens", 2000),
        "stream": True,
    }

    resp = requests.post(
        f"{_cfg.GROQ_BASE_URL}/chat/completions",
        headers=_groq_headers(),
        json=payload,
        timeout=60,
        stream=True,
    )
    resp.raise_for_status()

    for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        if not raw_line.startswith("data:"):
            continue
        data_str = raw_line[len("data:"):].strip()
        if data_str == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
        except Exception:
            continue
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if content:
            yield content


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
# Unified entry point — OpenRouter first, Groq fallback
# ---------------------------------------------------------------------------

def ask_ai(
    user_message: str,
    vector_memory: str = "",
    web_context: str = "",
    mode: dict | None = None,
    recent_history: list | None = None,
) -> str:
    """
    Unified AI call. Tries OpenRouter first; falls back to Groq on failure.

    Parameters match ask_groq / ask_openrouter exactly.

    Returns
    -------
    str — the assistant's reply.
    """
    mode = mode or {}

    # If no OpenRouter key is configured, skip directly to Groq
    if not _cfg.OPENROUTER_API_KEY:
        return ask_groq(user_message, vector_memory, web_context, mode, recent_history)

    # Try OpenRouter first
    try:
        return ask_openrouter(user_message, mode, vector_memory, web_context, recent_history)
    except Exception as exc:
        # Log the OpenRouter failure and fall back to Groq
        import logging
        _log = logging.getLogger(__name__)
        _log.warning("OpenRouter inference failed, falling back to Groq: %s", exc)
        return ask_groq(user_message, vector_memory, web_context, mode, recent_history)


def ask_ai_stream(
    user_message: str,
    vector_memory: str = "",
    web_context: str = "",
    mode: dict | None = None,
    recent_history: list | None = None,
):
    """
    v2.1 — Unified STREAMING AI call ("AI text tracker").

    Yields text chunks (deltas) as they're generated, instead of
    returning the full string at once. Tries OpenRouter streaming first,
    falls back to Groq streaming, and — if both fail before producing any
    output — falls back to a single non-streamed `ask_ai()` call so the
    caller always gets *something*.

    Parameters match `ask_ai()` exactly.
    """
    mode = mode or {}
    import logging
    _log = logging.getLogger(__name__)

    if _cfg.OPENROUTER_API_KEY:
        try:
            yielded_any = False
            for chunk in ask_openrouter_stream(user_message, mode, vector_memory, web_context, recent_history):
                yielded_any = True
                yield chunk
            if yielded_any:
                return
        except Exception as exc:
            _log.warning("OpenRouter streaming failed, falling back to Groq stream: %s", exc)

    if _cfg.GROQ_API_KEY:
        try:
            yielded_any = False
            for chunk in ask_groq_stream(user_message, vector_memory, web_context, mode, recent_history):
                yielded_any = True
                yield chunk
            if yielded_any:
                return
        except Exception as exc:
            _log.warning("Groq streaming failed, falling back to non-streamed response: %s", exc)

    # Last resort: one non-streamed call, delivered as a single chunk.
    text = ask_ai(user_message, vector_memory, web_context, mode, recent_history)
    if text:
        yield text


# Keep ask_groq available as a direct import for backward compatibility
__all__ = ["ask_ai", "ask_ai_stream", "ask_openrouter", "ask_groq", "ask_groq_vision"]
