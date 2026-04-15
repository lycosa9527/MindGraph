"""Robot outbound: group + O2O send, media helpers (OpenAPI v1.0 + oapi upload)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from services.mindbot.platforms.dingtalk.api.constants import (
    PATH_ROBOT_GROUP_MESSAGES_SEND,
    PATH_ROBOT_OTO_MESSAGES_BATCH_SEND,
)
from services.mindbot.platforms.dingtalk.api.http import post_v1_json
from services.mindbot.platforms.dingtalk.media.media_upload import upload_media_oapi
from services.mindbot.platforms.dingtalk.messaging.robot_templates import (
    msg_param_sample_action_card,
    msg_param_sample_audio,
    msg_param_sample_file,
    msg_param_sample_image,
    msg_param_sample_link,
    msg_param_sample_markdown,
    msg_param_sample_text,
    msg_param_sample_video,
)

async def send_group_robot_message(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    msg_key: str,
    msg_param: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """
    POST ``/v1.0/robot/groupMessages/send``.

    Returns response JSON (may include ``processQueryKey``) or ``None`` on failure.

    https://open.dingtalk.com/document/orgapp/the-robot-sends-a-group-message
    """
    payload = {
        "msgKey": msg_key.strip(),
        "msgParam": json.dumps(msg_param, ensure_ascii=False),
        "openConversationId": open_conversation_id.strip(),
        "robotCode": robot_code.strip(),
    }
    status, body = await post_v1_json(
        PATH_ROBOT_GROUP_MESSAGES_SEND,
        access_token,
        payload,
    )
    if status != 200:
        return None
    return body


async def send_oto_robot_message(
    access_token: str,
    robot_code: str,
    user_staff_ids: list[str],
    msg_key: str,
    msg_param: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """
    POST ``/v1.0/robot/oToMessages/batchSend``.

    https://open.dingtalk.com/document/orgapp/robots-send-one-on-one-messages
    """
    ids = [x.strip() for x in user_staff_ids if x.strip()]
    if not ids:
        return None
    payload = {
        "robotCode": robot_code.strip(),
        "userIds": ids,
        "msgKey": msg_key.strip(),
        "msgParam": json.dumps(msg_param, ensure_ascii=False),
    }
    status, body = await post_v1_json(
        PATH_ROBOT_OTO_MESSAGES_BATCH_SEND,
        access_token,
        payload,
    )
    if status != 200:
        return None
    return body


async def send_group_text_sample(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    text: str,
) -> Optional[dict[str, Any]]:
    return await send_group_robot_message(
        access_token,
        robot_code,
        open_conversation_id,
        "sampleText",
        msg_param_sample_text(text),
    )


async def send_private_text_sample(
    access_token: str,
    robot_code: str,
    user_staff_ids: list[str],
    text: str,
) -> Optional[dict[str, Any]]:
    return await send_oto_robot_message(
        access_token,
        robot_code,
        user_staff_ids,
        "sampleText",
        msg_param_sample_text(text),
    )


async def send_group_image_by_photo_url(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    photo_url: str,
) -> Optional[dict[str, Any]]:
    return await send_group_robot_message(
        access_token,
        robot_code,
        open_conversation_id,
        "sampleImageMsg",
        msg_param_sample_image(photo_url),
    )


async def send_private_image_by_photo_url(
    access_token: str,
    robot_code: str,
    user_staff_ids: list[str],
    photo_url: str,
) -> Optional[dict[str, Any]]:
    return await send_oto_robot_message(
        access_token,
        robot_code,
        user_staff_ids,
        "sampleImageMsg",
        msg_param_sample_image(photo_url),
    )


async def send_group_link_sample(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    text: str,
    title: str,
    message_url: str,
    pic_url: str = "",
) -> Optional[dict[str, Any]]:
    return await send_group_robot_message(
        access_token,
        robot_code,
        open_conversation_id,
        "sampleLink",
        msg_param_sample_link(text, title, message_url, pic_url),
    )


async def send_private_link_sample(
    access_token: str,
    robot_code: str,
    user_staff_ids: list[str],
    text: str,
    title: str,
    message_url: str,
    pic_url: str = "",
) -> Optional[dict[str, Any]]:
    return await send_oto_robot_message(
        access_token,
        robot_code,
        user_staff_ids,
        "sampleLink",
        msg_param_sample_link(text, title, message_url, pic_url),
    )


async def send_group_action_card_sample(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    title: str,
    text: str,
    single_title: str,
    single_url: str,
) -> Optional[dict[str, Any]]:
    return await send_group_robot_message(
        access_token,
        robot_code,
        open_conversation_id,
        "sampleActionCard",
        msg_param_sample_action_card(title, text, single_title, single_url),
    )


async def send_private_action_card_sample(
    access_token: str,
    robot_code: str,
    user_staff_ids: list[str],
    title: str,
    text: str,
    single_title: str,
    single_url: str,
) -> Optional[dict[str, Any]]:
    return await send_oto_robot_message(
        access_token,
        robot_code,
        user_staff_ids,
        "sampleActionCard",
        msg_param_sample_action_card(title, text, single_title, single_url),
    )


async def send_group_file_from_upload(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    file_bytes: bytes,
    filename: str,
) -> Optional[dict[str, Any]]:
    mid = await upload_media_oapi(access_token, "file", file_bytes, filename)
    if not mid:
        return None
    ext = Path(filename).suffix.lstrip(".").lower() or "bin"
    return await send_group_robot_message(
        access_token,
        robot_code,
        open_conversation_id,
        "sampleFile",
        msg_param_sample_file(mid, filename, ext),
    )


async def send_private_file_from_upload(
    access_token: str,
    robot_code: str,
    user_staff_ids: list[str],
    file_bytes: bytes,
    filename: str,
) -> Optional[dict[str, Any]]:
    mid = await upload_media_oapi(access_token, "file", file_bytes, filename)
    if not mid:
        return None
    ext = Path(filename).suffix.lstrip(".").lower() or "bin"
    return await send_oto_robot_message(
        access_token,
        robot_code,
        user_staff_ids,
        "sampleFile",
        msg_param_sample_file(mid, filename, ext),
    )


async def send_group_audio_from_upload(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    voice_bytes: bytes,
    filename: str,
    duration_ms: int,
) -> Optional[dict[str, Any]]:
    mid = await upload_media_oapi(access_token, "voice", voice_bytes, filename)
    if not mid:
        return None
    return await send_group_robot_message(
        access_token,
        robot_code,
        open_conversation_id,
        "sampleAudio",
        msg_param_sample_audio(mid, duration_ms),
    )


async def send_private_audio_from_upload(
    access_token: str,
    robot_code: str,
    user_staff_ids: list[str],
    voice_bytes: bytes,
    filename: str,
    duration_ms: int,
) -> Optional[dict[str, Any]]:
    mid = await upload_media_oapi(access_token, "voice", voice_bytes, filename)
    if not mid:
        return None
    return await send_oto_robot_message(
        access_token,
        robot_code,
        user_staff_ids,
        "sampleAudio",
        msg_param_sample_audio(mid, duration_ms),
    )


async def send_group_video_from_upload(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    video_bytes: bytes,
    video_filename: str,
    pic_bytes: bytes,
    pic_filename: str,
    duration_sec: int,
) -> Optional[dict[str, Any]]:
    vid = await upload_media_oapi(access_token, "video", video_bytes, video_filename)
    pic = await upload_media_oapi(access_token, "image", pic_bytes, pic_filename)
    if not vid or not pic:
        return None
    return await send_group_robot_message(
        access_token,
        robot_code,
        open_conversation_id,
        "sampleVideo",
        msg_param_sample_video(duration_sec, vid, pic),
    )


async def send_private_video_from_upload(
    access_token: str,
    robot_code: str,
    user_staff_ids: list[str],
    video_bytes: bytes,
    video_filename: str,
    pic_bytes: bytes,
    pic_filename: str,
    duration_sec: int,
) -> Optional[dict[str, Any]]:
    vid = await upload_media_oapi(access_token, "video", video_bytes, video_filename)
    pic = await upload_media_oapi(access_token, "image", pic_bytes, pic_filename)
    if not vid or not pic:
        return None
    return await send_oto_robot_message(
        access_token,
        robot_code,
        user_staff_ids,
        "sampleVideo",
        msg_param_sample_video(duration_sec, vid, pic),
    )


async def send_group_markdown_sample(
    access_token: str,
    robot_code: str,
    open_conversation_id: str,
    title: str,
    text: str,
) -> Optional[dict[str, Any]]:
    return await send_group_robot_message(
        access_token,
        robot_code,
        open_conversation_id,
        "sampleMarkdown",
        msg_param_sample_markdown(title, text),
    )


async def send_private_markdown_sample(
    access_token: str,
    robot_code: str,
    user_staff_ids: list[str],
    title: str,
    text: str,
) -> Optional[dict[str, Any]]:
    return await send_oto_robot_message(
        access_token,
        robot_code,
        user_staff_ids,
        "sampleMarkdown",
        msg_param_sample_markdown(title, text),
    )
