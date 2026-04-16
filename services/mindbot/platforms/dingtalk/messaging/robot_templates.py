"""``msgParam`` dicts for enterprise robot template keys (msgKey).

Templates align with:
https://open.dingtalk.com/document/orgapp/the-message-types-of-the-robot-sends-messages
"""

from __future__ import annotations

from typing import Any


def _clip(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    if n <= 1:
        return "…"
    return s[: n - 1] + "…"


def msg_param_sample_text(content: str) -> dict[str, Any]:
    return {"content": _clip(content, 5000)}


def msg_param_sample_markdown(title: str, text: str) -> dict[str, Any]:
    return {"title": _clip(title, 80), "text": _clip(text, 5000)}


def msg_param_sample_image(photo_url: str) -> dict[str, Any]:
    return {"photoURL": photo_url.strip()[:2048]}


def msg_param_sample_link(
    text: str,
    title: str,
    message_url: str,
    pic_url: str = "",
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "text": _clip(text, 5000),
        "title": _clip(title, 500),
        "messageUrl": message_url.strip()[:2048],
    }
    if pic_url.strip():
        out["picUrl"] = pic_url.strip()[:2048]
    return out


def msg_param_sample_action_card(
    title: str,
    text: str,
    single_title: str,
    single_url: str,
) -> dict[str, Any]:
    return {
        "title": _clip(title, 500),
        "text": _clip(text, 5000),
        "singleTitle": _clip(single_title, 200),
        "singleURL": single_url.strip()[:2048],
    }


def msg_param_sample_audio(media_id: str, duration_ms: int) -> dict[str, Any]:
    try:
        dur = max(1, int(duration_ms))
    except (ValueError, TypeError):
        dur = 1
    return {
        "mediaId": media_id.strip(),
        "duration": str(dur),
    }


def msg_param_sample_file(media_id: str, file_name: str, file_type: str) -> dict[str, Any]:
    return {
        "mediaId": media_id.strip(),
        "fileName": file_name.strip()[:255],
        "fileType": file_type.strip().lstrip(".")[:32],
    }


def msg_param_sample_video(
    duration_sec: int,
    video_media_id: str,
    pic_media_id: str,
    video_type: str = "mp4",
) -> dict[str, Any]:
    try:
        dur = max(1, int(duration_sec))
    except (ValueError, TypeError):
        dur = 1
    return {
        "duration": str(dur),
        "videoMediaId": video_media_id.strip(),
        "videoType": video_type.strip()[:16],
        "picMediaId": pic_media_id.strip(),
    }
