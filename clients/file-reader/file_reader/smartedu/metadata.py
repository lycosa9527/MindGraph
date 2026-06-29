# Mirrors chrome-extension/doc-extract/smartedu/metadata.js — keep ti_items walk rules in sync.

"""Fetch SmartEdu detail JSON and extract downloadable assets."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from file_reader.smartedu.models import SmartEduAsset, SmartEduLesson
from file_reader.smartedu.url_parser import ParsedSmartEduUrl, SmartEduUrlKind

M3U8_FLAGS = ("href-m3u8", "href")
PDF_FLAG = "pdf"
TARGET_TYPES = (
    "micro_lesson_video",
    "coursewares",
    "lesson_plandesign",
    "learning_task",
)
M3U8_RESOLUTION_ORDER = ("1920x1080", "1280x720", "852x480", "640x360")


def _localized_title(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("zh-CN", "zh_CN", "zh"):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _custom_props(resource: dict[str, Any]) -> dict[str, Any]:
    props = resource.get("custom_properties")
    return props if isinstance(props, dict) else {}


def _pick_m3u8_item(items: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    candidates: list[tuple[int, dict[str, Any]]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        flag = str(item.get("ti_file_flag") or "")
        fmt = str(item.get("ti_format") or "")
        if fmt != "m3u8" or flag not in M3U8_FLAGS:
            continue
        storages = item.get("ti_storages")
        if not isinstance(storages, list) or not storages:
            continue
        url = str(storages[0] or "")
        if not url:
            continue
        rank = 0
        if flag == "href-m3u8":
            rank += 100
        for index, token in enumerate(M3U8_RESOLUTION_ORDER):
            if token in url:
                rank += (len(M3U8_RESOLUTION_ORDER) - index) * 10
                break
        candidates.append((rank, item))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


def _pick_pdf_item(items: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("ti_file_flag") or "") != PDF_FLAG:
            continue
        storages = item.get("ti_storages")
        if isinstance(storages, list) and storages:
            return item
    return None


def _storage_url(item: dict[str, Any]) -> str:
    storages = item.get("ti_storages")
    if not isinstance(storages, list):
        return ""
    for entry in storages:
        text = str(entry or "").strip()
        if text:
            return text
    return ""


def _asset_from_resource(resource: dict[str, Any]) -> Optional[SmartEduAsset]:
    resource_type = str(resource.get("resource_type_code") or "")
    if resource_type not in TARGET_TYPES:
        return None

    props = _custom_props(resource)
    alias = str(props.get("alias_name") or resource.get("title") or resource_type)
    title = _localized_title(resource.get("global_title")) or str(resource.get("title") or alias)

    items = resource.get("ti_items")
    if not isinstance(items, list):
        return None

    if resource_type == "micro_lesson_video":
        picked = _pick_m3u8_item(items)
        if picked is None:
            return None
        download_url = _storage_url(picked)
        file_format = "mp4"
    else:
        picked = _pick_pdf_item(items)
        if picked is None:
            return None
        download_url = _storage_url(picked)
        file_format = "pdf"

    if not download_url:
        return None

    asset_id = str(resource.get("id") or resource.get("version_id") or title)
    return SmartEduAsset(
        asset_id=asset_id,
        title=title,
        alias=alias,
        resource_type=resource_type,
        format=file_format,
        download_url=download_url,
    )


def extract_assets_from_detail(detail: dict[str, Any]) -> list[SmartEduAsset]:
    """Walk relations.* and return the four standard lesson assets."""
    relations = detail.get("relations")
    if not isinstance(relations, dict):
        return []

    resources = relations.get("national_course_resource")
    if not isinstance(resources, list):
        return []

    assets: list[SmartEduAsset] = []
    seen_types: set[str] = set()
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        asset = _asset_from_resource(resource)
        if asset is None:
            continue
        if asset.resource_type in seen_types:
            continue
        seen_types.add(asset.resource_type)
        assets.append(asset)

    order = {name: index for index, name in enumerate(TARGET_TYPES)}
    assets.sort(key=lambda item: order.get(item.resource_type, 99))
    return assets


def lesson_title_from_detail(detail: dict[str, Any]) -> str:
    """Resolve display title from detail JSON."""
    title = _localized_title(detail.get("global_title"))
    if title:
        return title
    return str(detail.get("title") or detail.get("id") or "SmartEdu lesson")


def build_lesson(parsed: ParsedSmartEduUrl, detail: dict[str, Any]) -> SmartEduLesson:
    """Combine parse result and detail JSON into a lesson model."""
    lesson_id = str(detail.get("id") or parsed.resource_id)
    return SmartEduLesson(
        lesson_id=lesson_id,
        title=lesson_title_from_detail(detail),
        detail_url=parsed.detail_url,
        assets=extract_assets_from_detail(detail),
    )


def fetch_detail_json(
    detail_url: str,
    *,
    timeout: int = 30,
    opener: Optional[Callable[..., Any]] = None,
) -> dict[str, Any]:
    """GET detail JSON from SmartEdu CDN."""
    request = Request(
        detail_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "MindGraph-FileReader/1.0",
        },
        method="GET",
    )
    open_fn = opener or urlopen
    try:
        with open_fn(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"HTTP {exc.code}: {body[:200]}") from exc
    except URLError as exc:
        raise ValueError(f"Network error: {exc.reason}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Detail response is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Detail response must be a JSON object")
    return data


def load_lesson_from_detail_file(path: str) -> SmartEduLesson:
    """Load a lesson from a local fixture or cached detail JSON."""
    with open(path, encoding="utf-8") as handle:
        detail = json.load(handle)
    if not isinstance(detail, dict):
        raise ValueError("Fixture must be a JSON object")
    lesson_id = str(detail.get("id") or "fixture")
    parsed = ParsedSmartEduUrl(
        kind=SmartEduUrlKind.CLASS_ACTIVITY,
        resource_id=lesson_id,
        detail_url=f"fixture://{path}",
    )
    return build_lesson(parsed, detail)


def fetch_lesson(parsed: ParsedSmartEduUrl, *, timeout: int = 30) -> SmartEduLesson:
    """Fetch detail JSON and extract assets."""
    detail = fetch_detail_json(parsed.detail_url, timeout=timeout)
    return build_lesson(parsed, detail)
