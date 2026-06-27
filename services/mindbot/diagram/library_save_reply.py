"""Inject library-save skip notices into MindBot DingTalk outbound replies."""

from __future__ import annotations

import re
from typing import Optional

from services.diagram.assistant_markdown import (
    answer_has_library_diagram_uuid,
    extract_preview_unique_id,
)
from services.diagram.generation_skip_registry import get_generation_library_skip
from services.diagram.library_save_user_notices import library_save_user_notice

_LIBRARY_SAVE_SKIP_NOTICE_RE = re.compile(
    r"(?:Diagram preview only|导图仅预览|library save failed|图库保存失败|"
    r"图库已满|library is full|绑定钉钉|bind DingTalk|X-MG-Dify-User|"
    r"Link DingTalk|联系.*管理员|MindBot 配置)",
    re.IGNORECASE,
)


def extract_dingtalk_preview_unique_id(text: str) -> Optional[str]:
    """Return temp PNG unique id from generate_dingtalk preview URL in markdown."""
    return extract_preview_unique_id(text)


def answer_has_library_save_skip_notice(text: str) -> bool:
    """True when a library save skip notice is already present."""
    return _LIBRARY_SAVE_SKIP_NOTICE_RE.search((text or "").strip()) is not None


async def enrich_dingtalk_reply_with_library_save_notice(answer: str) -> str:
    """
    Prepend a user-facing skip notice when the reply has a preview image without library save.

    Looks up skip metadata recorded at generate_dingtalk time. Never raises.
    """
    raw = (answer or "").strip()
    if not raw:
        return answer
    if answer_has_library_diagram_uuid(raw):
        return answer
    if answer_has_library_save_skip_notice(raw):
        return answer
    unique_id = extract_dingtalk_preview_unique_id(raw)
    if not unique_id:
        return answer
    skip_data = await get_generation_library_skip(unique_id)
    if not skip_data:
        return answer
    reason = skip_data.get("reason", "")
    language = skip_data.get("language", "zh")
    notice = library_save_user_notice(reason, language, audience="dingtalk")
    if not notice.strip():
        return answer
    return f"{notice.strip()}\n\n{raw}"


def extract_prepended_library_save_notice(original: str, enriched: str) -> Optional[str]:
    """Return notice prefix added by enrich, or None when unchanged."""
    raw = (original or "").strip()
    enr = (enriched or "").strip()
    if not raw or enr == (original or ""):
        return None
    if not enr.endswith(raw):
        return None
    prefix = enr[: -len(raw)].strip()
    return prefix or None
