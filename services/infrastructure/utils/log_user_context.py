"""Request-scoped actor identity appended to backend log lines.

``auth_context_middleware`` and WebSocket auth bind the current user so
``UnifiedFormatter`` can show ``user=Name(id)`` without changing each call site.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Optional

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")
_MAX_NAME_LEN = 64


@dataclass(frozen=True)
class BoundLogUser:
    """Actor pinned for the current task."""

    user_id: int
    name: str


_log_user: ContextVar[BoundLogUser | None] = ContextVar("log_user", default=None)


def _clean_name(raw: Any) -> str:
    """Strip controls and collapse whitespace for a single log token."""
    text = str(raw or "").strip()
    text = _CONTROL_RE.sub(" ", text)
    text = " ".join(text.split())
    text = text.replace("|", "/")
    if len(text) > _MAX_NAME_LEN:
        text = text[:_MAX_NAME_LEN].rstrip()
    return text


def display_name_for_log(user: Any) -> str:
    """Prefer profile name, then phone or email."""
    name = _clean_name(getattr(user, "name", None))
    if name:
        return name
    phone = _clean_name(getattr(user, "phone", None))
    if phone:
        return phone
    return _clean_name(getattr(user, "email", None))


def _parse_user_id(user: Any) -> Optional[int]:
    """Return an int id, or None when missing or invalid."""
    raw = getattr(user, "id", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def bind_log_user(user: Any) -> Token[BoundLogUser | None]:
    """Pin actor id and display name for the current task."""
    if user is None:
        return _log_user.set(None)
    user_id = _parse_user_id(user)
    if user_id is None:
        return _log_user.set(None)
    return _log_user.set(BoundLogUser(user_id=user_id, name=display_name_for_log(user)))


def reset_log_user(token: Token[BoundLogUser | None] | None) -> None:
    """Restore the previous actor identity."""
    if token is None:
        return
    _log_user.reset(token)


def format_log_user_suffix() -> str:
    """Return `` user=Name(id)`` or `` user=id`` when an actor is bound."""
    try:
        bound = _log_user.get()
    except LookupError:
        return ""
    if bound is None:
        return ""
    if bound.name:
        return f" user={bound.name}({bound.user_id})"
    return f" user={bound.user_id}"
