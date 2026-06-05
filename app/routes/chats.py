"""
app/routes/chats.py
===================
Chat session management API (RESTful):
  GET    /api/chats              — list all chats for the user
  POST   /api/chats/create       — create a new chat session
  GET    /api/chats/<id>         — get a single chat
  PUT    /api/chats/<id>         — update a chat (messages, title, mode)
  DELETE /api/chats/<id>         — delete a chat
  POST   /api/chats/<id>/pin    — toggle pin status
  POST   /api/chats/<id>/rename — rename a chat
  POST   /api/chats/<id>/restore — restore chat (bump to top)
  GET    /api/chats/search?q=... — search chats

v4.0 changes:
  - All endpoints are auth-protected
  - Added /pin, /rename, /restore endpoints
  - Added search functionality
  - Returns are JSON-consistent
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.db import (
    db_create_chat,
    db_delete_chat,
    db_get_chat,
    db_get_user_chats,
    db_rename_chat,
    db_restore_chat,
    db_search_chats,
    db_toggle_pin,
    db_update_chat,
)

chats_bp = Blueprint("chats", __name__, url_prefix="/api/chats")


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _require_auth():
    """Return user_id or a JSON error response tuple."""
    uid = session.get("user_id")
    if not uid:
        return None, (jsonify({"ok": False, "error": "Not authenticated."}), 401)
    return uid, None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@chats_bp.route("", methods=["GET"])
def list_chats():
    """GET /api/chats — list all chats for the authenticated user."""
    user_id, err = _require_auth()
    if err:
        return err

    try:
        chats = db_get_user_chats(user_id)
        return jsonify({"ok": True, "chats": chats})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@chats_bp.route("/create", methods=["POST"])
def create_chat():
    """POST /api/chats/create — create a new chat session."""
    user_id, err = _require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "New chat").strip()
    mode = data.get("mode", "researcher")
    messages = data.get("messages", [])

    try:
        chat_id = db_create_chat(user_id, title, mode, messages)
        return jsonify({"ok": True, "chat_id": chat_id})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@chats_bp.route("/<chat_id>", methods=["GET"])
def get_chat(chat_id: str):
    """GET /api/chats/<id> — get a single chat session."""
    user_id, err = _require_auth()
    if err:
        return err

    try:
        chat = db_get_chat(chat_id)
        if not chat:
            return jsonify({"ok": False, "error": "Chat not found."}), 404
        if str(chat["user_id"]) != user_id:
            return jsonify({"ok": False, "error": "Access denied."}), 403
        return jsonify({"ok": True, "chat": chat})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@chats_bp.route("/<chat_id>", methods=["PUT"])
def update_chat(chat_id: str):
    """PUT /api/chats/<id> — update chat (messages, title, mode)."""
    user_id, err = _require_auth()
    if err:
        return err

    try:
        chat = db_get_chat(chat_id)
        if not chat:
            return jsonify({"ok": False, "error": "Chat not found."}), 404
        if str(chat["user_id"]) != user_id:
            return jsonify({"ok": False, "error": "Access denied."}), 403
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    data = request.get_json(silent=True) or {}
    title = data.get("title")
    messages = data.get("messages")
    mode = data.get("mode")

    try:
        db_update_chat(chat_id, title=title, messages=messages, mode=mode)
        return jsonify({"ok": True, "message": "Chat updated."})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@chats_bp.route("/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id: str):
    """DELETE /api/chats/<id> — permanently delete a chat."""
    user_id, err = _require_auth()
    if err:
        return err

    try:
        chat = db_get_chat(chat_id)
        if not chat:
            return jsonify({"ok": False, "error": "Chat not found."}), 404
        if str(chat["user_id"]) != user_id:
            return jsonify({"ok": False, "error": "Access denied."}), 403
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    try:
        db_delete_chat(chat_id)
        return jsonify({"ok": True, "message": "Chat deleted."})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# v4.0: Pin / Unpin
# ---------------------------------------------------------------------------


@chats_bp.route("/<chat_id>/pin", methods=["POST"])
def pin_chat(chat_id: str):
    """POST /api/chats/<id>/pin — toggle pin status."""
    user_id, err = _require_auth()
    if err:
        return err

    try:
        chat = db_get_chat(chat_id)
        if not chat:
            return jsonify({"ok": False, "error": "Chat not found."}), 404
        if str(chat["user_id"]) != user_id:
            return jsonify({"ok": False, "error": "Access denied."}), 403

        new_pinned = db_toggle_pin(chat_id)
        return jsonify({"ok": True, "pinned": new_pinned})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# v4.0: Rename
# ---------------------------------------------------------------------------


@chats_bp.route("/<chat_id>/rename", methods=["POST"])
def rename_chat(chat_id: str):
    """POST /api/chats/<id>/rename — rename a chat."""
    user_id, err = _require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    new_title = (data.get("title") or "").strip()
    if not new_title:
        return jsonify({"ok": False, "error": "Title is required."}), 400
    if len(new_title) > 120:
        return jsonify({"ok": False, "error": "Title too long (max 120 chars)."}), 400

    try:
        chat = db_get_chat(chat_id)
        if not chat:
            return jsonify({"ok": False, "error": "Chat not found."}), 404
        if str(chat["user_id"]) != user_id:
            return jsonify({"ok": False, "error": "Access denied."}), 403

        db_rename_chat(chat_id, new_title)
        return jsonify({"ok": True, "title": new_title})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# v4.0: Restore (bump to top)
# ---------------------------------------------------------------------------


@chats_bp.route("/<chat_id>/restore", methods=["POST"])
def restore_chat(chat_id: str):
    """POST /api/chats/<id>/restore — restore chat by bumping updated_at."""
    user_id, err = _require_auth()
    if err:
        return err

    try:
        chat = db_get_chat(chat_id)
        if not chat:
            return jsonify({"ok": False, "error": "Chat not found."}), 404
        if str(chat["user_id"]) != user_id:
            return jsonify({"ok": False, "error": "Access denied."}), 403

        db_restore_chat(chat_id)
        return jsonify({"ok": True, "message": "Chat restored."})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# v4.0: Search
# ---------------------------------------------------------------------------


@chats_bp.route("/search", methods=["GET"])
def search_chats():
    """GET /api/chats/search?q=query — search user's chats."""
    user_id, err = _require_auth()
    if err:
        return err

    query = (request.args.get("q") or "").strip()
    if not query or len(query) < 2:
        return jsonify({"ok": False, "error": "Search query must be at least 2 characters."}), 400

    try:
        chats = db_search_chats(user_id, query)
        return jsonify({"ok": True, "chats": chats, "query": query})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
