"""Normalize school-pasted API roots and join official protocol paths."""

from __future__ import annotations

from urllib.parse import urlparse

_STRIP_SUFFIXES = (
    "/chat/completions",
    "/completions",
    "/responses",
    "/messages",
)

_BLOCKED_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.goog",
        "169.254.169.254",
    }
)


def normalize_api_root(raw: str) -> str:
    """Strip whitespace, trailing slash, and a known protocol suffix."""
    root = (raw or "").strip()
    if not root:
        return ""
    while root.endswith("/"):
        root = root[:-1]
    lowered = root.lower()
    for suffix in _STRIP_SUFFIXES:
        if lowered.endswith(suffix):
            root = root[: -len(suffix)]
            while root.endswith("/"):
                root = root[:-1]
            break
    return root


def validated_api_root(raw: str) -> str:
    """Return a usable http(s) API root, or empty when the school URL is unsafe."""
    root = normalize_api_root(raw)
    if not root:
        return ""
    parsed = urlparse(root)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if parsed.username or parsed.password:
        return ""
    host = (parsed.hostname or "").strip().lower()
    if not host or host in _BLOCKED_HOSTS:
        return ""
    return root


def openai_chat_base_url(raw: str) -> str:
    """Root for AsyncOpenAI (appends ``/chat/completions``)."""
    return normalize_api_root(raw)


def openai_responses_url(raw: str) -> str:
    """Official ``POST {root}/responses`` URL."""
    root = normalize_api_root(raw)
    if not root:
        return ""
    return f"{root}/responses"


def anthropic_messages_url(raw: str) -> str:
    """Official ``POST {root}/messages`` URL (adds ``/v1`` when missing)."""
    root = normalize_api_root(raw)
    if not root:
        return ""
    if root.endswith("/messages"):
        return root
    if root.endswith("/v1"):
        return f"{root}/messages"
    return f"{root}/v1/messages"
