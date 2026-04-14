"""Parse Dify SSE payloads for MindBot native media (message_file, TTS)."""

from __future__ import annotations

import base64
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _workflow_file_keys_from_env() -> list[str]:
    raw = os.getenv("MINDBOT_DIFY_WORKFLOW_FILE_KEYS", "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]

_IMAGE_TYPES = frozenset(
    {
        "image",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/gif",
        "image/webp",
    }
)


def _norm_type(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    s = raw.strip().lower()
    if s.startswith("image"):
        return "image"
    return s


def parse_message_file_event(ev: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Extract assistant file info from ``message_file`` SSE event.

    Returns ``{"url": str, "type": str, "file_id": str|None}`` or None if unusable.
    Tries ``data`` (nested) then top-level fields (Dify variants).
    """
    data = ev.get("data")
    blob: dict[str, Any] = data if isinstance(data, dict) else {}
    if not blob:
        blob = ev

    url = (
        blob.get("url")
        or blob.get("remote_url")
        or blob.get("source_url")
        or ev.get("url")
    )
    if not isinstance(url, str) or not url.strip():
        return None
    url_s = url.strip()

    raw_type = blob.get("type") or blob.get("mime_type") or blob.get("extension")
    type_s = _norm_type(raw_type)
    if not type_s and isinstance(raw_type, str) and raw_type.strip():
        type_s = raw_type.strip().lower()

    fid = blob.get("id") or blob.get("file_id")
    file_id = fid.strip() if isinstance(fid, str) else None
    fn_raw = blob.get("filename") or blob.get("name")
    filename = fn_raw.strip() if isinstance(fn_raw, str) else ""

    if not type_s:
        if url_s.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            type_s = "image"
        else:
            type_s = "document"

    return {"url": url_s, "type": type_s, "file_id": file_id, "filename": filename}


def is_image_file_type(type_s: str) -> bool:
    t = (type_s or "").strip().lower()
    if t in _IMAGE_TYPES or t == "image":
        return True
    return t.startswith("image/")


def parse_tts_audio_base64_chunk(ev: dict[str, Any]) -> Optional[bytes]:
    """Return decoded audio bytes from ``tts_message`` chunk, or None."""
    data = ev.get("data")
    blob: dict[str, Any] = data if isinstance(data, dict) else {}
    if not blob:
        blob = ev

    raw = blob.get("audio") or blob.get("data") or ev.get("audio")
    if isinstance(raw, bytes):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return base64.b64decode(raw, validate=False)
    except (ValueError, TypeError) as exc:
        logger.debug("[MindBot] tts_message b64 decode failed: %s", exc)
        return None


def workflow_outputs_file_hints(outputs: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Collect file-like entries from workflow ``outputs`` for DingTalk follow-up sends.

    Supports:
    - List values: list of dicts with ``url``
    - Dict values: nested dicts with ``url`` and optional ``type`` / ``filename``
    """
    out: list[dict[str, Any]] = []
    explicit_keys = _workflow_file_keys_from_env()

    def push_from_obj(obj: Any) -> None:
        if isinstance(obj, dict):
            u = obj.get("url") or obj.get("file_url")
            if isinstance(u, str) and u.strip():
                t = obj.get("type") or obj.get("mime_type") or "document"
                fn = obj.get("filename") or obj.get("name") or ""
                out.append(
                    {
                        "url": u.strip(),
                        "type": str(t).strip().lower(),
                        "filename": str(fn) if fn else "",
                    }
                )

    for key in explicit_keys:
        if key in outputs:
            val = outputs[key]
            if isinstance(val, list):
                for item in val:
                    push_from_obj(item)
            else:
                push_from_obj(val)

    for val in outputs.values():
        if isinstance(val, list):
            for item in val:
                push_from_obj(item)
        elif isinstance(val, dict):
            push_from_obj(val)

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in out:
        u = item.get("url")
        if isinstance(u, str) and u not in seen:
            seen.add(u)
            deduped.append(item)
    return deduped


def parse_blocking_message_files(resp: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract assistant file attachments from blocking ``/chat-messages`` JSON.

    Checks ``metadata.message_files``, top-level ``message_files``, and
    ``metadata.files``.
    """
    out: list[dict[str, Any]] = []
    meta = resp.get("metadata")
    if not isinstance(meta, dict):
        meta = {}

    candidates: list[Any] = []
    for key in ("message_files", "files", "attachments"):
        v = meta.get(key)
        if isinstance(v, list):
            candidates.extend(v)
    top = resp.get("message_files")
    if isinstance(top, list):
        candidates.extend(top)

    for item in candidates:
        if not isinstance(item, dict):
            continue
        u = item.get("url") or item.get("preview_url") or item.get("source_url")
        if not isinstance(u, str) or not u.strip():
            continue
        t = item.get("type") or item.get("mime_type") or "document"
        fn = item.get("filename") or item.get("name") or ""
        out.append(
            {
                "url": u.strip(),
                "type": str(t).strip().lower(),
                "filename": str(fn) if fn else "",
            }
        )
    return out
