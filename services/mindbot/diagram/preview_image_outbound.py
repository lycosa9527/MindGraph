"""Deliver generate_dingtalk preview PNGs in DingTalk via OpenAPI sampleImageMsg."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.outbound.media import send_openapi_image_by_url

logger = logging.getLogger(__name__)

_PREVIEW_MD_RE = re.compile(
    r"!\[[^\]]*\]\((https://[^)\s]+/api/temp_images/dingtalk_[^)\s]+)\)",
    re.IGNORECASE,
)
_MG_DIAGRAM_COMMENT_RE = re.compile(
    r"<!--\s*mg-diagram-id:[^>]+-->\s*",
    re.IGNORECASE,
)


def extract_dingtalk_diagram_preview_url(text: str) -> Optional[str]:
    """Return HTTPS temp_images URL from a generate_dingtalk markdown line."""
    match = _PREVIEW_MD_RE.search((text or "").strip())
    if not match:
        return None
    url = match.group(1).strip()
    if not url.lower().startswith("https://"):
        return None
    return url


def strip_dingtalk_diagram_preview_markdown(text: str) -> str:
    """Remove preview image markdown and HTML comment carriers from card text."""
    cleaned = _PREVIEW_MD_RE.sub("", (text or ""))
    cleaned = _MG_DIAGRAM_COMMENT_RE.sub("", cleaned)
    lines = [line.rstrip() for line in cleaned.splitlines()]
    compact = "\n".join(line for line in lines if line.strip())
    return compact.strip()


def rewrite_dingtalk_diagram_markdown_alt(text: str) -> str:
    """Use empty alt text — DingTalk markdown mishandles ``![mg:uuid](url)``."""
    return _PREVIEW_MD_RE.sub(r"![](\1)", (text or ""))


def dingtalk_reply_text_without_inline_preview(text: str) -> str:
    """Return markdown for text/card delivery; preview PNG is sent separately."""
    card_md, preview_url = prepare_dingtalk_diagram_card_markdown(text)
    if preview_url:
        return card_md if card_md.strip() else " "
    return rewrite_dingtalk_diagram_markdown_alt(text)


def prepare_dingtalk_diagram_card_markdown(text: str) -> tuple[str, Optional[str]]:
    """
    Split card markdown from the preview PNG URL.

    AI card templates often fail to render signed temp URLs inline; the PNG is
    sent separately via ``sampleImageMsg``.
    """
    raw = (text or "").strip()
    url = extract_dingtalk_diagram_preview_url(raw)
    if not url:
        return rewrite_dingtalk_diagram_markdown_alt(raw), None
    card_md = strip_dingtalk_diagram_preview_markdown(raw)
    return card_md, url


async def maybe_send_dingtalk_diagram_preview_image(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    reply_text: str,
    *,
    pipeline_ctx: str = "",
) -> bool:
    """Send preview PNG via DingTalk OpenAPI when reply embeds a temp_images URL."""
    url = extract_dingtalk_diagram_preview_url(reply_text)
    if not url:
        return False
    ok, token_failed = await send_openapi_image_by_url(
        cfg,
        body,
        url,
        pipeline_ctx=pipeline_ctx,
        skip_fallback_gate=True,
    )
    if not ok:
        logger.warning(
            "[MindBot] diagram_preview_image_failed %s token_failed=%s url=%s",
            pipeline_ctx,
            token_failed,
            url[:120],
        )
    return ok
