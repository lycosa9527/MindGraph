"""Normalize DingTalk robot HTTP callback bodies into text for Dify (blocking chat).

Inbound shapes follow DingTalk docs and common callback variants:
- [接收消息](https://developers.dingtalk.com/document/robots/receive-message-1)
- [机器人接收消息](https://developers.dingtalk.com/document/dingstart/robot-receive-message)

Non-text media: identifiers are embedded in the prompt; optional OpenAPI download
and Dify upload are implemented in ``pipeline.callback`` when Client ID is configured.

``DingTalkInboundMessage``
--------------------------
Parse the raw ``body`` dict **once** at the callback entry point and carry the
structured message through the pipeline.  This eliminates repeated ``.get()``
chains across ``callback.py``, ``text.py``, and ``education/metrics.py``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_MAX_PROMPT = 48000
_MAX_JSON_SNIPPET = 4000


@dataclass(slots=True)
class DingTalkInboundMessage:
    """
    Normalized view of one DingTalk robot callback body.

    Parse once with :func:`parse_inbound_message` at the callback entry point;
    pass the instance through the pipeline instead of the raw ``body`` dict.
    The raw ``body`` is still available for callers that need full access (e.g.
    card delivery helpers that inspect arbitrary nested fields).
    """

    sender_staff_id: str
    sender_nick: str | None
    sender_id: str | None
    conversation_id: str
    conversation_type: str
    chat_type: str
    msg_id: str | None
    session_webhook: str | None
    inbound_msg_type: str
    text_in: str


def parse_inbound_message(body: dict[str, Any]) -> DingTalkInboundMessage:
    """
    Extract all pipeline-relevant fields from ``body`` in a single pass.

    Field resolution follows DingTalk's documented camelCase names and the
    snake_case aliases that some SDK versions emit.
    """
    staff, nick, sid = extract_dingtalk_sender_profile(body)

    conv_raw = body.get("conversationId") or body.get("conversation_id") or ""
    conversation_id = conv_raw.strip() if isinstance(conv_raw, str) else str(conv_raw).strip()

    ct_raw = body.get("conversationType") or body.get("conversation_type") or ""
    conversation_type = str(ct_raw).strip()
    if conversation_type == "2":
        chat_type = "group"
    elif conversation_type == "1":
        chat_type = "1:1"
    else:
        chat_type = ""

    mid_raw = body.get("msgId") or body.get("msg_id")
    msg_id = mid_raw.strip() if isinstance(mid_raw, str) and mid_raw.strip() else None

    sw_raw = body.get("sessionWebhook") or body.get("session_webhook")
    session_webhook = sw_raw.strip() if isinstance(sw_raw, str) and sw_raw.strip() else None

    text_in, inbound_msg_type = extract_inbound_prompt(body)

    return DingTalkInboundMessage(
        sender_staff_id=staff,
        sender_nick=nick,
        sender_id=sid,
        conversation_id=conversation_id,
        conversation_type=conversation_type,
        chat_type=chat_type,
        msg_id=msg_id,
        session_webhook=session_webhook,
        inbound_msg_type=inbound_msg_type,
        text_in=text_in,
    )


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _content_dict(body: dict[str, Any]) -> dict[str, Any]:
    raw = body.get("content")
    if isinstance(raw, dict):
        return raw
    return {}


def _json_snippet(obj: Any) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(obj)
    if len(s) > _MAX_JSON_SNIPPET:
        return s[:_MAX_JSON_SNIPPET] + "…"
    return s


def _normalize_msgtype(body: dict[str, Any]) -> str:
    raw = body.get("msgtype") or body.get("msgType")
    if not isinstance(raw, str) or not raw.strip():
        return "text"
    return raw.strip().lower()


def _is_group_conversation(body: dict[str, Any]) -> bool:
    ct = body.get("conversationType") or body.get("conversation_type")
    if ct is None:
        return False
    s = str(ct).strip().lower()
    return s in ("2", "group")


def _strip_leading_at_mentions(text: str) -> str:
    """Remove leading ``@name`` tokens used when mentioning the robot in group chats."""
    if not text:
        return text
    t = text.replace("\u200b", "").replace("\ufeff", "")
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"^\s*@\S+", "", t).lstrip()
    return t


def _maybe_strip_group_mentions(text: str, body: dict[str, Any]) -> str:
    if not _is_group_conversation(body):
        return text
    return _strip_leading_at_mentions(text)


def extract_inbound_prompt(body: dict[str, Any]) -> tuple[str, str]:
    """
    Build a UTF-8 prompt for Dify and return (prompt, normalized_msg_type).

    Handles text, picture/image, video, audio/voice, file, richText, link,
    markdown, and unknown (JSON snippet).
    """
    mt = _normalize_msgtype(body)
    if mt in ("picture", "image", "pic"):
        prompt = _extract_picture(body)
        return _clip(prompt), "picture"
    if mt == "video":
        prompt = _extract_video(body)
        return _clip(prompt), "video"
    if mt in ("audio", "voice"):
        prompt = _extract_audio(body)
        return _clip(prompt), "audio"
    if mt == "file":
        prompt = _extract_file(body)
        return _clip(prompt), "file"
    if mt in ("richtext", "rich_text", "richText"):
        prompt = _extract_rich_text(body)
        return _clip(prompt), "richText"
    if mt == "link":
        prompt = _maybe_strip_group_mentions(_extract_link(body), body)
        return _clip(prompt), "link"
    if mt == "markdown":
        prompt = _maybe_strip_group_mentions(_extract_markdown(body), body)
        return _clip(prompt), "markdown"
    if mt == "text":
        prompt = _maybe_strip_group_mentions(_extract_plain_text(body), body)
        return _clip(prompt), "text"
    prompt = _maybe_strip_group_mentions(_extract_unknown(mt, body), body)
    return _clip(prompt), mt


def _clip(text: str) -> str:
    if len(text) <= _MAX_PROMPT:
        return text
    return text[:_MAX_PROMPT] + "…"


def extract_dingtalk_sender_profile(body: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """
    Return ``(sender_staff_id, sender_nick, sender_id)`` from a robot callback body.

    DingTalk commonly sends ``senderStaffId``, ``senderNick``, and ``senderId``; field
    names may vary by protocol version.
    """
    raw_staff = body.get("senderStaffId") or body.get("sender_staff_id")
    if raw_staff is None:
        staff = ""
    elif isinstance(raw_staff, str):
        staff = raw_staff.strip()
    else:
        staff = str(raw_staff).strip()
    if not staff:
        staff = "unknown"

    nick_raw = (
        body.get("senderNick") or body.get("sender_nick") or body.get("senderNickName") or body.get("sender_nickname")
    )
    if isinstance(nick_raw, str) and nick_raw.strip():
        sender_nick = nick_raw.strip()
    else:
        sender_nick = None

    sid_raw = body.get("senderId") or body.get("sender_id")
    if isinstance(sid_raw, str) and sid_raw.strip():
        sender_id = sid_raw.strip()
    else:
        sender_id = None

    return staff, sender_nick, sender_id


def _extract_plain_text(body: dict[str, Any]) -> str:
    text_obj = body.get("text")
    if isinstance(text_obj, dict):
        raw = text_obj.get("content", "")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    top = body.get("content")
    if isinstance(top, str) and top.strip():
        return top.strip()
    return ""


def _extract_picture(body: dict[str, Any]) -> str:
    cd = _content_dict(body)
    pic = _as_str(
        cd.get("pictureDownloadCode") or cd.get("picture_download_code") or body.get("pictureDownloadCode"),
    )
    dcode = _as_str(cd.get("downloadCode") or cd.get("download_code") or body.get("downloadCode"))
    media_id = _as_str(cd.get("mediaId") or cd.get("media_id"))
    lines = [
        "[DingTalk picture message] The user sent an image.",
        "Media bytes are not included in the HTTP callback; use DingTalk OpenAPI "
        "to download by downloadCode / pictureDownloadCode when needed.",
    ]
    if pic:
        lines.append(f"pictureDownloadCode={pic}")
    if dcode:
        lines.append(f"downloadCode={dcode}")
    if media_id:
        lines.append(f"mediaId={media_id}")
    if len(lines) == 2:
        lines.append(f"raw.content={_json_snippet(cd) if cd else _json_snippet(body)}")
    return "\n".join(lines)


def _extract_video(body: dict[str, Any]) -> str:
    cd = _content_dict(body)
    vid = body.get("video")
    if isinstance(vid, dict):
        blob = vid
    else:
        blob = cd if cd else {}
    parts = [
        "[DingTalk video message] The user sent a video.",
        _json_snippet(blob) if blob else _json_snippet(body),
    ]
    return "\n".join(parts)


def _extract_audio(body: dict[str, Any]) -> str:
    cd = _content_dict(body)
    aud = body.get("audio") or body.get("voice")
    if isinstance(aud, dict):
        blob = aud
    else:
        blob = cd if cd else {}
    parts = [
        "[DingTalk audio message] The user sent a voice/audio message.",
        _json_snippet(blob) if blob else _json_snippet(body),
    ]
    return "\n".join(parts)


def _extract_file(body: dict[str, Any]) -> str:
    cd = _content_dict(body)
    fi = body.get("file")
    if isinstance(fi, dict):
        blob = fi
    else:
        blob = cd if cd else {}
    file_id = _as_str(
        (blob.get("fileId") if isinstance(blob, dict) else None) or body.get("fileId") or cd.get("fileId"),
    )
    name = _as_str((blob.get("fileName") if isinstance(blob, dict) else None) or cd.get("fileName"))
    lines = ["[DingTalk file message] The user sent a file."]
    if name:
        lines.append(f"fileName={name}")
    if file_id:
        lines.append(f"fileId={file_id}")
    lines.append(_json_snippet(blob) if blob else _json_snippet(body))
    return "\n".join(lines)


def _extract_rich_text(body: dict[str, Any]) -> str:
    rt = body.get("richText") or body.get("rich_text")
    if rt is None:
        rt = body.get("content")
    return "[DingTalk richText message]\n" + _json_snippet(rt)


def _extract_link(body: dict[str, Any]) -> str:
    lk = body.get("link")
    if not isinstance(lk, dict):
        lk = _content_dict(body)
    title = _as_str(lk.get("title"))
    text = _as_str(lk.get("text"))
    url = _as_str(lk.get("messageUrl") or lk.get("message_url") or lk.get("url"))
    pic = _as_str(lk.get("picUrl") or lk.get("pic_url"))
    parts = ["[DingTalk link message]"]
    if title:
        parts.append(f"title={title}")
    if text:
        parts.append(f"text={text}")
    if url:
        parts.append(f"url={url}")
    if pic:
        parts.append(f"picUrl={pic}")
    if len(parts) == 1:
        parts.append(_json_snippet(lk))
    return "\n".join(parts)


def _extract_markdown(body: dict[str, Any]) -> str:
    md = body.get("markdown")
    if isinstance(md, dict):
        title = _as_str(md.get("title"))
        text = _as_str(md.get("text"))
        parts = ["[DingTalk markdown message]"]
        if title:
            parts.append(f"title={title}")
        if text:
            parts.append("body:\n" + text)
        return "\n".join(parts) if len(parts) > 1 else _extract_plain_text(body)
    return _extract_plain_text(body)


def _extract_unknown(mt: str, body: dict[str, Any]) -> str:
    fallback = _extract_plain_text(body)
    if fallback:
        return f"[DingTalk msgtype={mt}]\n{fallback}"
    copied = {k: v for k, v in body.items() if k not in ("text", "markdown", "link")}
    return f"[DingTalk message msgtype={mt}]\nStructured summary (truncated):\n{_json_snippet(copied)}"


def extract_download_code_for_openapi(body: dict[str, Any], normalized_msg_type: str) -> str:
    """
    Return a single ``downloadCode`` for ``/v1.0/robot/messageFiles/download``.

    Prefer ``pictureDownloadCode`` for images when present.
    """
    cd = _content_dict(body)
    if normalized_msg_type == "picture":
        pic = _as_str(
            cd.get("pictureDownloadCode")
            or cd.get("picture_download_code")
            or cd.get("downloadCode")
            or cd.get("download_code"),
        )
        if pic:
            return pic
    vid = body.get("video")
    if isinstance(vid, dict):
        c = _as_str(vid.get("downloadCode") or vid.get("download_code"))
        if c:
            return c
    aud = body.get("audio") or body.get("voice")
    if isinstance(aud, dict):
        c = _as_str(aud.get("downloadCode") or aud.get("download_code"))
        if c:
            return c
    fi = body.get("file")
    if isinstance(fi, dict):
        c = _as_str(fi.get("downloadCode") or fi.get("download_code"))
        if c:
            return c
    return _as_str(
        cd.get("downloadCode") or cd.get("download_code") or body.get("downloadCode"),
    )


def media_filename_and_types(
    normalized_msg_type: str,
    body: dict[str, Any],
) -> tuple[str, str, str]:
    """
    Guess (filename, mime_type, dify_file_type) for Dify upload.

    dify_file_type: image | video | audio | document
    """
    cd = _content_dict(body)
    if normalized_msg_type == "picture":
        return ("dingtalk_image.jpg", "image/jpeg", "image")
    if normalized_msg_type == "video":
        return ("dingtalk_video.mp4", "video/mp4", "video")
    if normalized_msg_type in ("audio",):
        return ("dingtalk_audio.amr", "audio/amr", "audio")
    name = _as_str(cd.get("fileName") or cd.get("file_name"))
    if not name:
        name = "dingtalk_file.bin"
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else "bin"
    mime = "application/octet-stream"
    if ext in ("pdf",):
        mime = "application/pdf"
    elif ext in ("doc", "docx"):
        mime = (
            "application/msword"
            if ext == "doc"
            else ("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        )
    elif ext in ("xlsx", "xls"):
        mime = (
            "application/vnd.ms-excel"
            if ext == "xls"
            else ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        )
    return (name, mime, "document")
