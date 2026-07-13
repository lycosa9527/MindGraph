"""Kitty Session Manager shared types (snapshot, alignment, journal).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class KittyAlignment(str, Enum):
    """Cross-device scope alignment for a requested diagram scope."""

    ALIGNED_LIBRARY = "aligned_library"
    ALIGNED_EPHEMERAL = "aligned_ephemeral"
    PROMOTING = "promoting"
    SCOPE_DIVERGENCE = "scope_divergence"
    MISMATCH = "mismatch"
    DESKTOP_ONLY = "desktop_only"
    MOBILE_ONLY = "mobile_only"
    NO_OWNER = "no_owner"
    EMPTY = "empty"


class KittyIngressOwner(str, Enum):
    """Who owns typed/mic ingress when both UIs are open on the same scope."""

    MOBILE = "mobile"
    DESKTOP = "desktop"


@dataclass(slots=True)
class KittySessionSnapshot:
    """Unified pairing + alignment view for one user and a requested scope."""

    user_id: int
    requested_scope: str
    desktop_focus_library_id: Optional[str]
    desktop_focus_updated_at: Optional[int]
    mobile_active: bool
    mobile_scopes: List[str]
    mobile_primary_scope: Optional[str]
    canvas_owner_present: bool
    alignment: KittyAlignment
    ingress_owner: KittyIngressOwner
    error_code: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable snapshot for REST / debug."""
        return {
            "user_id": self.user_id,
            "requested_scope": self.requested_scope,
            "desktop_focus_library_id": self.desktop_focus_library_id,
            "desktop_focus_updated_at": self.desktop_focus_updated_at,
            "mobile_active": self.mobile_active,
            "mobile_scopes": list(self.mobile_scopes),
            "mobile_primary_scope": self.mobile_primary_scope,
            "canvas_owner_present": self.canvas_owner_present,
            "alignment": self.alignment.value,
            "ingress_owner": self.ingress_owner.value,
            "error_code": self.error_code,
        }


@dataclass(slots=True)
class KittyAlignResult:
    """Outcome of require_aligned_for_verified_edit."""

    ok: bool
    snapshot: KittySessionSnapshot
    error_code: Optional[str] = None
    message: str = ""


@dataclass(slots=True)
class KittyJournalEvent:
    """One hot-path Session Manager journal entry."""

    kind: str
    user_id: int
    diagram_scope: str
    ts: int
    lane: Optional[str] = None
    voice_session_id: Optional[str] = None
    request_id: Optional[str] = None
    parent_request_id: Optional[str] = None
    utterance_id: Optional[str] = None
    ingress_source: Optional[str] = None
    text_preview: Optional[str] = None
    text_len: Optional[int] = None
    action: Optional[str] = None
    mutation_id: Optional[str] = None
    hub_revision: Optional[int] = None
    outcome: Optional[str] = None
    library_id: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for Redis JSON."""
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value is not None}
