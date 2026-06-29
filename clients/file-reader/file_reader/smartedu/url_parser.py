# Mirrors chrome-extension/doc-extract/smartedu/url-parser.js — keep URL templates in sync.

"""Parse SmartEdu page URLs into detail API endpoints."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qs, urlparse

_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

DETAIL_HOST = "https://s-file-1.ykt.cbern.com.cn"


class SmartEduUrlKind(str, Enum):
    """Supported SmartEdu URL shapes."""

    CLASS_ACTIVITY = "class_activity"
    TCH_MATERIAL = "tch_material"
    PREPARE_DETAIL = "prepare_detail"
    QUALITY_COURSE = "quality_course"


@dataclass(frozen=True)
class ParsedSmartEduUrl:
    """Normalized SmartEdu URL parse result."""

    kind: SmartEduUrlKind
    resource_id: str
    detail_url: str


def _detail_path(kind: SmartEduUrlKind, resource_id: str) -> str:
    if kind == SmartEduUrlKind.CLASS_ACTIVITY:
        return f"/zxx/ndrv2/national_lesson/resources/details/{resource_id}.json"
    if kind == SmartEduUrlKind.TCH_MATERIAL:
        return f"/zxx/ndrv2/resources/tch_material/details/{resource_id}.json"
    if kind == SmartEduUrlKind.PREPARE_DETAIL:
        return f"/zxx/ndrv2/prepare_lesson/resources/details/{resource_id}.json"
    if kind == SmartEduUrlKind.QUALITY_COURSE:
        return f"/zxx/ndrv2/quality_course/resources/details/{resource_id}.json"
    raise ValueError(f"Unsupported URL kind: {kind}")


def _pick_uuid(params: dict[str, list[str]], *keys: str) -> str | None:
    for key in keys:
        values = params.get(key)
        if not values:
            continue
        candidate = values[0].strip()
        if _UUID.match(candidate):
            return candidate
    return None


def _kind_from_path(path: str) -> SmartEduUrlKind | None:
    lowered = path.lower()
    if "syncclassroom/classactivity" in lowered or "syncclassroom/class_activity" in lowered:
        return SmartEduUrlKind.CLASS_ACTIVITY
    if "tchmaterial/detail" in lowered:
        return SmartEduUrlKind.TCH_MATERIAL
    if "prepare/detail" in lowered:
        return SmartEduUrlKind.PREPARE_DETAIL
    if "qualitycourse" in lowered:
        return SmartEduUrlKind.QUALITY_COURSE
    return None


def parse_smartedu_url(raw_url: str) -> ParsedSmartEduUrl:
    """Parse a SmartEdu URL and return the detail JSON endpoint."""
    text = raw_url.strip()
    if not text:
        raise ValueError("URL is empty")

    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("URL must include scheme and host")

    kind = _kind_from_path(parsed.path)
    if kind is None:
        raise ValueError("Unsupported SmartEdu URL path")

    params = parse_qs(parsed.query, keep_blank_values=False)
    resource_keys = {
        SmartEduUrlKind.CLASS_ACTIVITY: ("activityId", "activityid"),
        SmartEduUrlKind.TCH_MATERIAL: ("contentId", "contentid", "id"),
        SmartEduUrlKind.PREPARE_DETAIL: ("lessonId", "lessonid", "contentId", "contentid"),
        SmartEduUrlKind.QUALITY_COURSE: ("courseId", "courseid", "teachingmaterialId", "contentId", "contentid"),
    }
    resource_id = _pick_uuid(params, *resource_keys[kind])
    if resource_id is None:
        raise ValueError(f"Missing resource id query parameter for {kind.value}")

    detail_path = _detail_path(kind, resource_id)
    return ParsedSmartEduUrl(
        kind=kind,
        resource_id=resource_id,
        detail_url=f"{DETAIL_HOST}{detail_path}",
    )
