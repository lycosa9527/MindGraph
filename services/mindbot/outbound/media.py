"""DingTalk OpenAPI sends for Dify-native media (image, voice, file, markdown snippet)."""

from __future__ import annotations

import io
import logging
import wave
from typing import Any

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.core.dify_sse_parse import (
    is_image_file_type,
    parse_blocking_message_files,
)
from services.mindbot.outbound.text import is_group_conversation
from services.mindbot.platforms.dingtalk import (
    get_access_token,
    send_group_audio_from_upload,
    send_group_file_from_upload,
    send_group_image_by_photo_url,
    send_group_markdown_sample,
    send_private_audio_from_upload,
    send_private_file_from_upload,
    send_private_image_by_photo_url,
    send_private_markdown_sample,
)
from services.mindbot.platforms.dingtalk.messaging.session_webhook import (
    markdown_title_and_body_for_openapi,
    sanitize_markdown_for_dingtalk,
)
from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)


async def send_openapi_image_by_url(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    photo_url: str,
    *,
    pipeline_ctx: str = "",
) -> tuple[bool, bool]:
    """Send ``sampleImageMsg``. Returns ``(success, token_failed)``."""
    if not env_bool("MINDBOT_OPENAPI_ENABLED", True):
        return False, False
    if not env_bool("MINDBOT_FALLBACK_OPENAPI_SEND", True):
        return False, False
    app_key = (cfg.dingtalk_client_id or "").strip()
    if not app_key:
        return False, False
    token = await get_access_token(
        cfg.organization_id,
        app_key,
        cfg.dingtalk_app_secret.strip(),
    )
    if not token:
        return False, True
    robot_code = cfg.dingtalk_robot_code.strip()
    sender = body.get("senderStaffId") or body.get("sender_staff_id")
    sender_s = sender.strip() if isinstance(sender, str) else ""
    conv_id = body.get("conversationId") or body.get("conversation_id")
    conv_s = conv_id.strip() if isinstance(conv_id, str) else ""
    url = photo_url.strip()[:2048]
    if not url.lower().startswith("https://"):
        logger.warning(
            "[MindBot] openapi_image_skip_non_https %s url=%s",
            pipeline_ctx,
            url[:80],
        )
        return False, False
    if is_group_conversation(body):
        if not conv_s:
            return False, False
        res = await send_group_image_by_photo_url(token, robot_code, conv_s, url)
        ok = res is not None
        if ok:
            logger.info(
                "[MindBot] outbound_openapi_image %s chat=group",
                pipeline_ctx,
            )
        return ok, False
    if not sender_s:
        return False, False
    res = await send_private_image_by_photo_url(token, robot_code, [sender_s], url)
    ok = res is not None
    if ok:
        logger.info("[MindBot] outbound_openapi_image %s chat=oto", pipeline_ctx)
    return ok, False


async def send_openapi_voice_bytes(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    voice_bytes: bytes,
    *,
    duration_ms: int,
    pipeline_ctx: str = "",
) -> tuple[bool, bool]:
    """Upload voice and send ``sampleAudio``."""
    if not env_bool("MINDBOT_OPENAPI_ENABLED", True):
        return False, False
    if not env_bool("MINDBOT_FALLBACK_OPENAPI_SEND", True):
        return False, False
    app_key = (cfg.dingtalk_client_id or "").strip()
    if not app_key:
        return False, False
    token = await get_access_token(
        cfg.organization_id,
        app_key,
        cfg.dingtalk_app_secret.strip(),
    )
    if not token:
        return False, True
    robot_code = cfg.dingtalk_robot_code.strip()
    sender = body.get("senderStaffId") or body.get("sender_staff_id")
    sender_s = sender.strip() if isinstance(sender, str) else ""
    conv_id = body.get("conversationId") or body.get("conversation_id")
    conv_s = conv_id.strip() if isinstance(conv_id, str) else ""
    filename = "tts.mp3"
    dur = max(1000, min(120_000, int(duration_ms)))
    if is_group_conversation(body):
        if not conv_s:
            return False, False
        res = await send_group_audio_from_upload(token, robot_code, conv_s, voice_bytes, filename, dur)
        ok = res is not None
        if ok:
            logger.info(
                "[MindBot] outbound_openapi_audio %s chat=group bytes=%s",
                pipeline_ctx,
                len(voice_bytes),
            )
        return ok, False
    if not sender_s:
        return False, False
    res = await send_private_audio_from_upload(token, robot_code, [sender_s], voice_bytes, filename, dur)
    ok = res is not None
    if ok:
        logger.info(
            "[MindBot] outbound_openapi_audio %s chat=oto bytes=%s",
            pipeline_ctx,
            len(voice_bytes),
        )
    return ok, False


async def send_openapi_file_bytes(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    file_bytes: bytes,
    filename: str,
    *,
    pipeline_ctx: str = "",
) -> tuple[bool, bool]:
    """Upload file media and send ``sampleFile``."""
    if not env_bool("MINDBOT_OPENAPI_ENABLED", True):
        return False, False
    if not env_bool("MINDBOT_FALLBACK_OPENAPI_SEND", True):
        return False, False
    app_key = (cfg.dingtalk_client_id or "").strip()
    if not app_key:
        return False, False
    token = await get_access_token(
        cfg.organization_id,
        app_key,
        cfg.dingtalk_app_secret.strip(),
    )
    if not token:
        return False, True
    robot_code = cfg.dingtalk_robot_code.strip()
    sender = body.get("senderStaffId") or body.get("sender_staff_id")
    sender_s = sender.strip() if isinstance(sender, str) else ""
    conv_id = body.get("conversationId") or body.get("conversation_id")
    conv_s = conv_id.strip() if isinstance(conv_id, str) else ""
    fn = filename.strip() or "file.bin"
    if is_group_conversation(body):
        if not conv_s:
            return False, False
        res = await send_group_file_from_upload(token, robot_code, conv_s, file_bytes, fn)
        ok = res is not None
        if ok:
            logger.info(
                "[MindBot] outbound_openapi_file %s chat=group bytes=%s",
                pipeline_ctx,
                len(file_bytes),
            )
        return ok, False
    if not sender_s:
        return False, False
    res = await send_private_file_from_upload(token, robot_code, [sender_s], file_bytes, fn)
    ok = res is not None
    if ok:
        logger.info(
            "[MindBot] outbound_openapi_file %s chat=oto bytes=%s",
            pipeline_ctx,
            len(file_bytes),
        )
    return ok, False


async def send_openapi_markdown_snippet(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    markdown_text: str,
    *,
    pipeline_ctx: str = "",
) -> tuple[bool, bool]:
    """Send a short ``sampleMarkdown`` bubble (e.g. file link)."""
    if not env_bool("MINDBOT_OPENAPI_ENABLED", True):
        return False, False
    if not env_bool("MINDBOT_FALLBACK_OPENAPI_SEND", True):
        return False, False
    app_key = (cfg.dingtalk_client_id or "").strip()
    if not app_key:
        return False, False
    token = await get_access_token(
        cfg.organization_id,
        app_key,
        cfg.dingtalk_app_secret.strip(),
    )
    if not token:
        return False, True
    robot_code = cfg.dingtalk_robot_code.strip()
    sender = body.get("senderStaffId") or body.get("sender_staff_id")
    sender_s = sender.strip() if isinstance(sender, str) else ""
    conv_id = body.get("conversationId") or body.get("conversation_id")
    conv_s = conv_id.strip() if isinstance(conv_id, str) else ""
    text = markdown_text if isinstance(markdown_text, str) else str(markdown_text)
    title, body_md = markdown_title_and_body_for_openapi(text)
    body_md = sanitize_markdown_for_dingtalk(body_md)
    if is_group_conversation(body):
        if not conv_s:
            return False, False
        res = await send_group_markdown_sample(token, robot_code, conv_s, title, body_md)
        ok = res is not None
        if ok:
            logger.info(
                "[MindBot] outbound_openapi_md_snippet %s chat=group",
                pipeline_ctx,
            )
        return ok, False
    if not sender_s:
        return False, False
    res = await send_private_markdown_sample(token, robot_code, [sender_s], title, body_md)
    ok = res is not None
    if ok:
        logger.info(
            "[MindBot] outbound_openapi_md_snippet %s chat=oto",
            pipeline_ctx,
        )
    return ok, False


async def send_dify_native_segment(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    kind: str,
    payload: dict[str, Any],
    *,
    pipeline_ctx: str = "",
) -> tuple[bool, bool]:
    """Dispatch one native segment from Dify stream (image, markdown, or voice)."""
    if kind == "image":
        url = payload.get("url")
        if not isinstance(url, str) or not url.strip():
            return True, False
        return await send_openapi_image_by_url(cfg, body, url, pipeline_ctx=pipeline_ctx)
    if kind == "markdown":
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return True, False
        return await send_openapi_markdown_snippet(cfg, body, text, pipeline_ctx=pipeline_ctx)
    if kind == "audio":
        raw = payload.get("bytes")
        if not isinstance(raw, (bytes, bytearray)):
            return True, False
        voice_bytes = bytes(raw)
        if not voice_bytes:
            return True, False
        try:
            dur = int(float(payload.get("duration_ms") or 0))
        except (TypeError, ValueError):
            dur = 0
        if dur <= 0:
            dur = estimate_voice_duration_ms(voice_bytes)
        return await send_openapi_voice_bytes(
            cfg,
            body,
            voice_bytes,
            duration_ms=dur,
            pipeline_ctx=pipeline_ctx,
        )
    return True, False


async def send_blocking_response_attachments(
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    resp: dict[str, Any],
    *,
    pipeline_ctx: str = "",
) -> tuple[bool, bool]:
    """
    After the main answer is delivered, send assistant files from blocking JSON.

    Returns ``(all_ok, token_failed)`` — ``token_failed`` if any step failed on token.
    """
    if not env_bool("MINDBOT_DIFY_NATIVE_MEDIA_ENABLED", True):
        return True, False
    if not env_bool("MINDBOT_OPENAPI_ENABLED", True):
        return True, False
    files = parse_blocking_message_files(resp)
    token_failed_any = False
    for item in files:
        url = item.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        type_s = str(item.get("type") or "document")
        fn = str(item.get("filename") or "")
        if is_image_file_type(type_s):
            ok, tf = await send_openapi_image_by_url(cfg, body, url, pipeline_ctx=pipeline_ctx)
            if tf:
                token_failed_any = True
            if not ok and not tf:
                return False, False
            continue
        link_md = f"[file]({url})"
        if fn:
            link_md = f"**{fn}**\n{link_md}"
        ok, tf = await send_openapi_markdown_snippet(cfg, body, link_md, pipeline_ctx=pipeline_ctx)
        if tf:
            token_failed_any = True
        if not ok and not tf:
            return False, False
    return True, token_failed_any


def estimate_voice_duration_ms(voice_bytes: bytes) -> int:
    """Best-effort duration for DingTalk ``sampleAudio``."""
    if len(voice_bytes) >= 12 and voice_bytes[:4] == b"RIFF":
        try:
            with wave.open(io.BytesIO(voice_bytes), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate() or 1
                return int(max(1000, min(120_000, 1000 * frames / rate)))
        except (wave.Error, ValueError, OSError):
            pass
    return int(max(1000, min(120_000, len(voice_bytes) // 16)))
