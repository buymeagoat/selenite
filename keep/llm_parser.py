"""LLM conversation parsers.

Converts exported conversations from ChatGPT, Claude, Gemini, and
plain-text chat logs into Selenite's transcript segment format.

Each parser returns a list of segment dicts::

    [
        {"id": 0, "start": 0.0, "end": 0.0, "text": "...", "speaker": "User"},
        {"id": 1, "start": 0.0, "end": 0.0, "text": "...", "speaker": "Assistant"},
        ...
    ]

start/end are always 0.0 because text conversations have no timeline.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Supported providers ──────────────────────────────────────

SUPPORTED_PROVIDERS = ("chatgpt", "claude", "gemini", "generic")


# ── Public API ───────────────────────────────────────────────


def detect_provider(raw: str) -> str:
    """Auto-detect the LLM export provider from raw text/JSON.

    Returns one of ``SUPPORTED_PROVIDERS`` or ``"generic"`` as fallback.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return "generic"

    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        # ChatGPT: list of conversation objects with "mapping" key
        if isinstance(first, dict) and "mapping" in first:
            return "chatgpt"
        # Claude: list of objects with "chat_messages" key
        if isinstance(first, dict) and "chat_messages" in first:
            return "claude"
        # Gemini: exported conversations are objects with
        # a top-level list containing dicts with "parts" arrays
    # Gemini single conversation with "parts" under each entry
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if isinstance(first, dict) and "parts" in first:
            return "gemini"

    return "generic"


def parse_conversation(
    raw: str,
    *,
    provider: str | None = None,
    conversation_index: int = 0,
) -> list[dict[str, Any]]:
    """Parse an LLM export into transcript segments.

    Parameters
    ----------
    raw : str
        The raw file content (JSON or plain text).
    provider : str | None
        Force a specific parser. ``None`` = auto-detect.
    conversation_index : int
        For exports containing multiple conversations, pick one (0-based).

    Returns
    -------
    list[dict]
        Segments in Selenite's canonical format.
    """
    if not raw or not raw.strip():
        raise ValueError("Empty input — nothing to parse.")

    if provider is None:
        provider = detect_provider(raw)

    parsers = {
        "chatgpt": _parse_chatgpt,
        "claude": _parse_claude,
        "gemini": _parse_gemini,
        "generic": _parse_generic,
    }
    parser = parsers.get(provider, _parse_generic)
    segments = parser(raw, conversation_index=conversation_index)

    if not segments:
        raise ValueError(
            f"No conversation turns found (provider={provider}). "
            "Check the file format or try a different provider."
        )
    return segments


def list_conversations(raw: str, *, provider: str | None = None) -> list[dict[str, Any]]:
    """Return metadata about conversations in a multi-conversation export.

    Returns a list like::

        [{"index": 0, "title": "My Chat", "message_count": 12}, ...]
    """
    if provider is None:
        provider = detect_provider(raw)

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return [{"index": 0, "title": "Pasted conversation", "message_count": None}]

    if provider == "chatgpt" and isinstance(data, list):
        convos = []
        for i, conv in enumerate(data):
            title = conv.get("title", f"Conversation {i + 1}")
            mapping = conv.get("mapping", {})
            count = sum(
                1
                for node in mapping.values()
                if isinstance(node, dict)
                and node.get("message")
                and node["message"].get("content", {}).get("parts")
            )
            convos.append({"index": i, "title": title, "message_count": count})
        return convos

    if provider == "claude" and isinstance(data, list):
        convos = []
        for i, conv in enumerate(data):
            title = conv.get("name", f"Conversation {i + 1}")
            msgs = conv.get("chat_messages", [])
            convos.append({"index": i, "title": title, "message_count": len(msgs)})
        return convos

    return [{"index": 0, "title": "Conversation", "message_count": None}]


# ── ChatGPT ──────────────────────────────────────────────────


def _parse_chatgpt(raw: str, *, conversation_index: int = 0) -> list[dict]:
    """Parse a ChatGPT ``conversations.json`` export.

    Structure: list of conversation objects.  Each has ``mapping`` — a dict
    of message-id → node.  We walk the linked list via ``parent``/``children``
    to reconstruct chronological order.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        # Plain text pasted instead of a JSON export — fall back to generic.
        return _parse_generic(raw, conversation_index=conversation_index)
    if not isinstance(data, list) or conversation_index >= len(data):
        return []

    conv = data[conversation_index]
    mapping = conv.get("mapping", {})

    # Build child→parent and parent→children maps, then walk from root
    ordered_messages: list[dict] = []
    children_map: dict[str, list[str]] = {}
    for nid, node in mapping.items():
        parent = node.get("parent")
        if parent:
            children_map.setdefault(parent, []).append(nid)

    # Find root node (no parent)
    root_ids = [nid for nid, node in mapping.items() if not node.get("parent")]
    if not root_ids:
        # Fallback: iterate all nodes
        root_ids = list(mapping.keys())[:1]

    # BFS walk
    queue = list(root_ids)
    visited = set()
    while queue:
        nid = queue.pop(0)
        if nid in visited:
            continue
        visited.add(nid)
        node = mapping.get(nid, {})
        msg = node.get("message")
        if msg and msg.get("content", {}).get("parts"):
            role = msg.get("author", {}).get("role", "unknown")
            parts = msg["content"]["parts"]
            text = "\n".join(p if isinstance(p, str) else str(p) for p in parts).strip()
            if text:
                ordered_messages.append({"role": role, "text": text})
        for child in children_map.get(nid, []):
            queue.append(child)

    return _to_segments(ordered_messages)


# ── Claude ───────────────────────────────────────────────────


def _parse_claude(raw: str, *, conversation_index: int = 0) -> list[dict]:
    """Parse a Claude export (JSON with ``chat_messages`` arrays).

    Each conversation object has ``chat_messages`` — a list of
    ``{"sender": "human"|"assistant", "text": "..."}``.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return _parse_generic(raw, conversation_index=conversation_index)
    if not isinstance(data, list) or conversation_index >= len(data):
        return []

    conv = data[conversation_index]
    messages = conv.get("chat_messages", [])

    ordered: list[dict] = []
    for msg in messages:
        sender = msg.get("sender", "unknown")
        # Claude exports sometimes nest content in "content" array
        text = msg.get("text") or ""
        if not text and isinstance(msg.get("content"), list):
            text = "\n".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in msg["content"]
            ).strip()
        if text.strip():
            role = _normalize_role(sender)
            ordered.append({"role": role, "text": text.strip()})

    return _to_segments(ordered)


# ── Gemini ───────────────────────────────────────────────────


def _parse_gemini(raw: str, *, conversation_index: int = 0) -> list[dict]:
    """Parse a Gemini/Bard export.

    Gemini exports are typically a list of turn objects, each with
    a ``"role"`` and ``"parts"`` array containing ``{"text": "..."}``.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return _parse_generic(raw, conversation_index=conversation_index)
    if not isinstance(data, list):
        return []

    ordered: list[dict] = []
    for entry in data:
        role_raw = entry.get("role", "unknown")
        parts = entry.get("parts", [])
        text = "\n".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in parts
        ).strip()
        if text:
            role = _normalize_role(role_raw)
            ordered.append({"role": role, "text": text})

    return _to_segments(ordered)


# ── Generic / Plain Text ─────────────────────────────────────

# Regex: lines like "User:", "Assistant:", "Human:", "AI:", "System:" etc.
_ROLE_LINE_RE = re.compile(
    r"^(User|Human|Assistant|AI|System|Model|Claude|ChatGPT|Gemini|GPT-4|GPT-3\.5)\s*:\s*",
    re.IGNORECASE | re.MULTILINE,
)


def _parse_generic(raw: str, *, conversation_index: int = 0) -> list[dict]:
    """Parse a plain-text conversation with ``Role: message`` lines.

    Also handles JSON arrays of ``{"role": ..., "content": ...}`` objects
    (common in API-log pastes).
    """
    # Try JSON first (list of {role, content} objects)
    try:
        data = json.loads(raw)
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, dict) and ("role" in first or "content" in first):
                ordered = []
                for msg in data:
                    role = _normalize_role(msg.get("role", "unknown"))
                    text = msg.get("content", "")
                    if isinstance(text, list):
                        text = "\n".join(
                            p.get("text", "") if isinstance(p, dict) else str(p) for p in text
                        )
                    if isinstance(text, str) and text.strip():
                        ordered.append({"role": role, "text": text.strip()})
                return _to_segments(ordered)
    except (json.JSONDecodeError, TypeError):
        pass

    # Plain text: split on role lines
    splits = _ROLE_LINE_RE.split(raw)
    if len(splits) < 3:
        # No role markers found — treat the entire text as a single entry
        return _to_segments([{"role": "User", "text": raw.strip()}]) if raw.strip() else []

    ordered: list[dict] = []
    # splits: ['', 'User', ' message\n', 'Assistant', ' reply\n', ...]
    i = 1
    while i < len(splits) - 1:
        role = _normalize_role(splits[i])
        text = splits[i + 1].strip()
        if text:
            ordered.append({"role": role, "text": text})
        i += 2

    return _to_segments(ordered)


# ── Helpers ──────────────────────────────────────────────────

_ROLE_MAP = {
    "user": "User",
    "human": "User",
    "system": "System",
    "assistant": "Assistant",
    "ai": "Assistant",
    "model": "Assistant",
    "claude": "Assistant",
    "chatgpt": "Assistant",
    "gemini": "Assistant",
    "gpt-4": "Assistant",
    "gpt-3.5": "Assistant",
    "tool": "Tool",
}


def _normalize_role(raw_role: str) -> str:
    """Map provider-specific role names to canonical labels."""
    return _ROLE_MAP.get(raw_role.lower().strip(), raw_role.strip().title())


def _to_segments(messages: list[dict]) -> list[dict]:
    """Convert ``[{"role": ..., "text": ...}]`` into Selenite segments."""
    return [
        {
            "id": idx,
            "start": 0.0,
            "end": 0.0,
            "text": msg["text"],
            "speaker": _normalize_role(msg["role"]),
        }
        for idx, msg in enumerate(messages)
    ]
