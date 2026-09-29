"""
Normalize a library-demo document before it is stored.

Drops broken lists and notes. Keeps text when the HTML is unsafe.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Literal

from models.requests.library_demo import (
    LibraryDemoCaptionModel,
    LibraryDemoDocumentModel,
    LibraryDemoListModel,
    LibraryDemoThumbnailModel,
)

_MAX_LISTS = 40
_MAX_NAME = 80
_MAX_IDS = 60
_MAX_TEXT = 8000
_MAX_HTML = 24000
_MAX_ID = 64
_MAX_CAPTIONS = 200
_MAX_THUMBS = 200
_THUMB_URL = re.compile(r"^/api/auth/library-demo/thumbnails/[A-Za-z0-9_-]{1,64}$")
_DANGEROUS_HTML = re.compile(r"<\s*/?\s*script|javascript\s*:|on[a-z]+\s*=", re.IGNORECASE)


def _clean_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > _MAX_ID:
        return None
    return cleaned


def _font_size(value: object) -> Literal[15, 18, 22, 28] | None:
    if value is None:
        return 18
    if value == 15:
        return 15
    if value == 18:
        return 18
    if value == 22:
        return 22
    if value == 28:
        return 28
    return None


def _font_color(value: object) -> Literal["ink", "stone", "brown", "red", "blue", "green"]:
    if value == "stone":
        return "stone"
    if value == "brown":
        return "brown"
    if value == "red":
        return "red"
    if value == "blue":
        return "blue"
    if value == "green":
        return "green"
    return "ink"


def _font_face(value: object) -> Literal["sans", "sc", "tc", "serif", "song", "kai", "mono"]:
    if value == "sc":
        return "sc"
    if value == "tc":
        return "tc"
    if value == "serif":
        return "serif"
    if value == "song":
        return "song"
    if value == "kai":
        return "kai"
    if value == "mono":
        return "mono"
    return "sans"


def _caption(value: object) -> LibraryDemoCaptionModel | None:
    if not isinstance(value, dict):
        return None
    text = value.get("text")
    if not isinstance(text, str):
        return None
    size = _font_size(value.get("fontSize", 18))
    if size is None:
        return None
    body: dict[str, object] = {
        "text": text.replace("\x00", "")[:_MAX_TEXT],
        "fontSize": size,
        "fontFace": _font_face(value.get("fontFace")),
        "fontColor": _font_color(value.get("fontColor")),
    }
    html = value.get("html")
    if isinstance(html, str) and html.strip() and _DANGEROUS_HTML.search(html) is None:
        body["html"] = html.replace("\x00", "")[:_MAX_HTML]
    return LibraryDemoCaptionModel.model_validate(body)


def _captions(value: object) -> dict[str, LibraryDemoCaptionModel]:
    if not isinstance(value, dict):
        return {}
    kept: dict[str, LibraryDemoCaptionModel] = {}
    for key, raw in value.items():
        diagram_id = _clean_id(key)
        draft = _caption(raw)
        if diagram_id is None or draft is None or diagram_id in kept:
            continue
        kept[diagram_id] = draft
        if len(kept) >= _MAX_CAPTIONS:
            break
    return kept


def _diagram_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    kept: list[str] = []
    for item in value:
        diagram_id = _clean_id(item)
        if diagram_id is None or diagram_id in kept:
            continue
        kept.append(diagram_id)
        if len(kept) >= _MAX_IDS:
            break
    return kept


def _lists(value: object) -> list[LibraryDemoListModel]:
    if not isinstance(value, list):
        return []
    kept: list[LibraryDemoListModel] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        list_id = _clean_id(item.get("id"))
        name = item.get("name")
        if list_id is None or list_id in seen or not isinstance(name, str) or not name.strip():
            continue
        seen.add(list_id)
        kept.append(
            LibraryDemoListModel.model_validate(
                {
                    "id": list_id,
                    "name": name.strip()[:_MAX_NAME],
                    "diagramIds": _diagram_ids(item.get("diagramIds")),
                    "captions": _captions(item.get("captions")),
                }
            )
        )
        if len(kept) >= _MAX_LISTS:
            break
    return kept


def _updated_at(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if len(cleaned) < 8 or len(cleaned) > 40 or not any(char.isdigit() for char in cleaned):
        return None
    return cleaned


def _thumbnails(value: object) -> dict[str, LibraryDemoThumbnailModel]:
    if not isinstance(value, dict):
        return {}
    kept: dict[str, LibraryDemoThumbnailModel] = {}
    for key, raw in value.items():
        diagram_id = _clean_id(key)
        if diagram_id is None or not isinstance(raw, dict) or diagram_id in kept:
            continue
        updated = _updated_at(raw.get("updatedAt"))
        if updated is None:
            continue
        url = raw.get("url", "")
        if url is None or url == "":
            kept[diagram_id] = LibraryDemoThumbnailModel.model_validate({"url": "", "updatedAt": updated})
        elif isinstance(url, str) and _THUMB_URL.fullmatch(url) is not None and url.endswith(f"/{diagram_id}"):
            kept[diagram_id] = LibraryDemoThumbnailModel.model_validate({"url": url, "updatedAt": updated})
        else:
            continue
        if len(kept) >= _MAX_THUMBS:
            break
    return kept


def normalize_library_demo(payload: object) -> LibraryDemoDocumentModel:
    """Return a document that is safe to store. Reject a non-object body."""
    if not isinstance(payload, dict):
        raise ValueError("library demo document must be an object")
    lists = _lists(payload.get("lists"))
    known = {item.id for item in lists}
    last_raw = payload.get("lastId")
    last_id = last_raw if isinstance(last_raw, str) and last_raw in known else None
    return LibraryDemoDocumentModel.model_validate(
        {
            "lists": lists,
            "lastId": last_id,
            "captions": _captions(payload.get("captions")),
            "thumbnails": _thumbnails(payload.get("thumbnails")),
        }
    )
