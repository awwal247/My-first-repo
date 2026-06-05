"""
app/services/memory.py
======================
TF-IDF + cosine-similarity vector memory retrieval.
Finds the most semantically relevant past exchanges for
injecting into the current AI prompt.
"""

import logging

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config.settings import Config

_log = logging.getLogger(__name__)
_cfg = Config()
TOP_K = _cfg.TOP_K_MEMORY


def retrieve_relevant_memory(
    user_id: str,
    mode_key: str,
    query: str,
    top_k: int = TOP_K,
) -> str:
    """
    Retrieve the most relevant past exchanges for the given query.

    Reads conversation history directly from the database via
    db.db_get_conversation, then applies TF-IDF vectorisation and
    cosine similarity to rank previous user messages against query.

    Parameters
    ----------
    user_id  : UUID string of the current user (from session["user_id"]).
    mode_key : AI mode key, e.g. "researcher".
    query    : The current user message to compare against.
    top_k    : Maximum number of past exchanges to return.

    Returns
    -------
    str
        A formatted block of relevant past exchanges, or "" if none found.
    """
    # 1. Short-circuit: blank query -> return the last 6 messages verbatim
    if not (query or "").strip():
        try:
            from app.services.db import db_get_conversation
            history = db_get_conversation(user_id, mode_key, limit=6)
        except RuntimeError as exc:
            _log.warning("retrieve_relevant_memory db error: %s", exc)
            return ""
        return _format_pairs(_build_pairs(history))

    # 2. Fetch history from DB
    try:
        from app.services.db import db_get_conversation
        history = db_get_conversation(user_id, mode_key, limit=60)
    except RuntimeError as exc:
        _log.warning("retrieve_relevant_memory db error: %s", exc)
        return ""

    if not history:
        return ""

    # 3. Short-circuit: fewer than 2 messages -> return everything
    if len(history) < 2:
        return _format_pairs(_build_pairs(history))

    # 4. Build (user_message, assistant_reply) pairs
    pairs = _build_pairs(history)
    if not pairs:
        return ""

    user_texts = [p[0] for p in pairs]

    # 5. TF-IDF scoring with ValueError fallback
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform(user_texts + [query])
        query_vec = matrix[-1]
        past_vecs = matrix[:-1]
        sims = cosine_similarity(query_vec, past_vecs).flatten()
    except ValueError:
        # Corpus too small / all stop-words -- return raw history as fallback
        return _format_pairs(pairs)

    ranked = np.argsort(sims)[::-1]
    selected = [idx for idx in ranked if sims[idx] > 0][:top_k]

    if not selected:
        return ""

    lines = []
    for idx in selected:
        user_q, asst_a = pairs[idx]
        lines.append(
            f"- User previously asked: {user_q}\n  You answered: {asst_a}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_pairs(history: list[dict]) -> list[tuple[str, str]]:
    """Build (user_message, assistant_reply) pairs from a flat message list."""
    pairs: list[tuple[str, str]] = []
    for i, msg in enumerate(history):
        if msg["role"] == "user":
            reply = ""
            if i + 1 < len(history) and history[i + 1]["role"] == "assistant":
                reply = history[i + 1]["content"]
            pairs.append((msg["content"], reply))
    return pairs


def _format_pairs(pairs: list[tuple[str, str]]) -> str:
    """Format pairs as a human-readable string."""
    if not pairs:
        return ""
    return "\n".join(
        f"- User previously asked: {u}\n  You answered: {a}"
        for u, a in pairs
    )
