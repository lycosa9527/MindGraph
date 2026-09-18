"""Learning Space helpers: class codes, initial passwords, AI permission merge.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
import secrets
import string
from typing import Any

from pypinyin import Style, lazy_pinyin

from models.domain.learning_space import (
    DEFAULT_AI_PERMISSIONS,
    GRANULAR_AI_CAPABILITIES,
    LEGACY_AI_CAPABILITY_ALIASES,
)
from services.learning_space.blank_spec import TEMPLATE_ROLES, resolve_template_role

_CLASS_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_NAME_CLEAN_RE = re.compile(r"\s+")


def normalize_student_name(name: str) -> str:
    """Trim and collapse whitespace in a student display name."""
    return _NAME_CLEAN_RE.sub(" ", (name or "").strip())


def generate_class_code(length: int = 6) -> str:
    """Generate an unambiguous classroom join code."""
    return "".join(secrets.choice(_CLASS_CODE_ALPHABET) for _ in range(length))


def initial_password_from_name(name: str) -> str:
    """Build default password: lowercase pinyin initials + ``123``."""
    cleaned = normalize_student_name(name)
    if not cleaned:
        return "xg123"
    initials: list[str] = []
    for ch in cleaned:
        if ch.isspace():
            continue
        if "A" <= ch <= "Z" or "a" <= ch <= "z":
            initials.append(ch.lower())
            continue
        if ch.isdigit():
            initials.append(ch)
            continue
        parts = lazy_pinyin(ch, style=Style.FIRST_LETTER)
        if parts and parts[0]:
            letter = parts[0][0]
            if letter in string.ascii_letters:
                initials.append(letter.lower())
    if not initials:
        initials = ["x", "g"]
    return "".join(initials) + "123"


def student_synthetic_email(class_id: int, user_id: int) -> str:
    """Stable unique email satisfying users.phone_or_email check."""
    return f"s{class_id}.{user_id}@student.learning.local"


STUDENT_SYNTHETIC_EMAIL_SUFFIX = "@student.learning.local"

_MAX_REFERENCE_DIAGRAMS = 5
_MAX_REFERENCE_THUMBNAIL_CHARS = 80_000


def _reference_diagrams_from_raw(raw: dict[str, Any]) -> list[dict[str, str]]:
    """Keep extra look-only diagrams (id / title / thumbnail) for student materials."""
    items = raw.get("reference_diagrams")
    if not isinstance(items, list):
        return []
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if len(cleaned) >= _MAX_REFERENCE_DIAGRAMS:
            break
        if not isinstance(item, dict):
            continue
        diagram_id = str(item.get("id") or "").strip()
        if not diagram_id or len(diagram_id) > 36 or diagram_id in seen:
            continue
        seen.add(diagram_id)
        thumb_raw = item.get("thumbnail")
        thumbnail = str(thumb_raw).strip() if isinstance(thumb_raw, str) else ""
        if len(thumbnail) > _MAX_REFERENCE_THUMBNAIL_CHARS:
            thumbnail = ""
        title = str(item.get("title") or "").strip()[:200]
        cleaned.append({"id": diagram_id, "title": title, "thumbnail": thumbnail})
    return cleaned


def is_learning_space_synthetic_email(email: str | None) -> bool:
    """True for Learning Space placeholder emails (not real email-login accounts)."""
    if not email or not isinstance(email, str):
        return False
    return email.strip().lower().endswith(STUDENT_SYNTHETIC_EMAIL_SUFFIX)


def merge_ai_permissions(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Merge assignment AI flags onto defaults; keep analysis/publish meta keys.

    Granular keys are the source of truth. Legacy keys on older rows are promoted
    into granular flags when the granular key was not explicitly set. Legacy keys
    are then mirrored from granular values for older consumers.
    """
    merged: dict[str, Any] = dict(DEFAULT_AI_PERMISSIONS)
    if not raw:
        return merged
    for key in DEFAULT_AI_PERMISSIONS:
        if key in raw:
            merged[key] = bool(raw[key])

    # Promote legacy → granular when older assignments only stored legacy keys.
    for legacy, granular in LEGACY_AI_CAPABILITY_ALIASES.items():
        if granular not in raw and legacy in raw and bool(raw[legacy]):
            merged[granular] = True

    # Older rows may grant tools without an explicit ai_assist flag.
    if "ai_assist" not in raw and any(bool(merged[k]) for k in GRANULAR_AI_CAPABILITIES):
        merged["ai_assist"] = True

    # Master switch off forces every canvas tool off.
    if not bool(merged.get("ai_assist")):
        for key in GRANULAR_AI_CAPABILITIES:
            merged[key] = False

    # Keep legacy mirrors in sync for older gate call sites / clients.
    merged["generate_diagram"] = bool(merged["topic_generate"])
    merged["node_palette"] = bool(merged["ai_brainstorm"])
    merged["inline_recommend"] = bool(merged["ai_brainstorm"])
    merged["doc_summary"] = bool(merged["file_generate"] or merged["web_generate"])

    dims = raw.get("evaluation_dimensions")
    if isinstance(dims, list):
        cleaned_dims = [str(item).strip() for item in dims if str(item).strip()]
        merged["evaluation_dimensions"] = cleaned_dims[:24]
    if "allow_late_submit" in raw:
        merged["allow_late_submit"] = bool(raw["allow_late_submit"])
    if "remind_24h" in raw:
        merged["remind_24h"] = bool(raw["remind_24h"])
    scheduled = raw.get("scheduled_publish_at")
    if isinstance(scheduled, str) and scheduled.strip():
        merged["scheduled_publish_at"] = scheduled.strip()
    diagram_type = raw.get("diagram_type")
    if isinstance(diagram_type, str) and diagram_type.strip():
        slug = diagram_type.strip()
        merged["diagram_type"] = "mind_map" if slug == "mindmap" else slug
    if "has_teacher_template" in raw:
        merged["has_teacher_template"] = bool(raw["has_teacher_template"])
    role_raw = raw.get("template_role")
    if isinstance(role_raw, str) and role_raw.strip() in TEMPLATE_ROLES:
        role = role_raw.strip()
        merged["template_role"] = role
        merged["start_mode"] = "scaffold" if role == "scaffold" else "blank"
        merged["has_teacher_template"] = role in {"reference", "scaffold"}
    elif raw.get("start_mode") in {"blank", "scaffold"}:
        merged["start_mode"] = str(raw["start_mode"])
        role = resolve_template_role(raw)
        merged["template_role"] = role
        if "has_teacher_template" not in raw:
            merged["has_teacher_template"] = role in {"reference", "scaffold"}
    references = _reference_diagrams_from_raw(raw)
    if references:
        merged["reference_diagrams"] = references
    return merged


def resolve_ai_capability(capability: str) -> str:
    """Map legacy capability names onto granular keys."""
    return LEGACY_AI_CAPABILITY_ALIASES.get(capability, capability)


def ai_permission_allowed(permissions: dict[str, Any] | None, capability: str) -> bool:
    """True when the assignment grants ``capability`` (honors ``ai_assist`` master)."""
    merged = merge_ai_permissions(permissions if isinstance(permissions, dict) else None)
    if not bool(merged.get("ai_assist")):
        return False
    resolved = resolve_ai_capability(capability)
    return bool(merged.get(resolved))
