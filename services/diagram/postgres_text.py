"""Strip U+0000 from values bound to PostgreSQL text and jsonb.

PostgreSQL rejects a null byte inside text and jsonb (``UntranslatableCharacter``).
``pg_json_dumps`` is the engine JSON serializer. It encodes first, then searches
that text for a real ``\\u0000`` escape. Clean values pay for the search only.
Collaboration flushes that ``CAST`` a pre-serialized string use the same
function, because that path never reaches the engine serializer. Diagram title
and thumbnail are plain text. ``postgres_diagram_payload`` cleans those, and
the spec, only when the size-check JSON or those strings contain a null. Redis
then stores the same object PostgreSQL gets.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_JSON_NUL_ESCAPE = "\\u0000"


def diagram_payload_needs_nul_strip(title: str, spec_json: str, thumbnail: str | None) -> bool:
    """True when a diagram write may contain U+0000.

    ``spec_json`` is ``json.dumps(spec)``. A literal backslash-u sequence in
    user text also matches; the walker then finds no null and returns the
    original spec.
    """
    if "\x00" in title:
        return True
    if isinstance(thumbnail, str) and "\x00" in thumbnail:
        return True
    return _JSON_NUL_ESCAPE in spec_json


def postgres_diagram_payload(
    title: str,
    spec: dict[str, Any],
    thumbnail: str | None,
) -> tuple[str, dict[str, Any], str | None]:
    """Drop U+0000 from a diagram title, spec, and thumbnail before a write."""
    cleaned_title = strip_postgres_nul(title)
    cleaned_spec = strip_postgres_nul(spec)
    cleaned_thumb = strip_postgres_nul(thumbnail) if isinstance(thumbnail, str) else thumbnail
    title_out = cleaned_title if isinstance(cleaned_title, str) else title
    spec_out = cleaned_spec if isinstance(cleaned_spec, dict) else spec
    thumb_out = cleaned_thumb if isinstance(cleaned_thumb, str) or cleaned_thumb is None else thumbnail
    if title_out is not title or spec_out is not spec or thumb_out is not thumbnail:
        logger.info("Removed U+0000 from diagram payload before PostgreSQL write")
    return title_out, spec_out, thumb_out


def pg_json_dumps(value: Any, **kwargs: Any) -> str:
    """JSON-encode ``value`` for PostgreSQL, dropping real U+0000 escapes."""
    dumped = json.dumps(value, **kwargs)
    if _JSON_NUL_ESCAPE not in dumped:
        return dumped
    return _drop_json_nul_escapes(dumped)


def _drop_json_nul_escapes(dumped: str) -> str:
    """Remove JSON ``\\u0000`` escapes. An encoded backslash (``\\\\``) stays."""
    parts: list[str] = []
    start = 0
    index = 0
    length = len(dumped)
    while index < length:
        if dumped[index] != "\\":
            index += 1
            continue
        if index + 1 < length and dumped[index + 1] == "\\":
            index += 2
            continue
        if dumped.startswith(_JSON_NUL_ESCAPE, index):
            parts.append(dumped[start:index])
            index += len(_JSON_NUL_ESCAPE)
            start = index
            continue
        index += 1
    parts.append(dumped[start:])
    return "".join(parts)


def strip_postgres_nul(value: Any) -> Any:
    """
    Return ``value`` with U+0000 removed from strings.

    Dicts, lists, and tuples are walked. The original object is returned when
    nothing changed.
    """
    if isinstance(value, str):
        if "\x00" not in value:
            return value
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return _strip_dict(value)
    if isinstance(value, list):
        return _strip_list(value)
    if isinstance(value, tuple):
        return _strip_tuple(value)
    return value


def _strip_dict(value: dict) -> dict:
    for key, item in value.items():
        new_key = strip_postgres_nul(key) if isinstance(key, str) else key
        if new_key is not key or strip_postgres_nul(item) is not item:
            return _rebuild_dict(value)
    return value


def _rebuild_dict(value: dict) -> dict:
    cleaned: dict = {}
    for key, item in value.items():
        new_key = strip_postgres_nul(key) if isinstance(key, str) else key
        cleaned[new_key] = strip_postgres_nul(item)
    return cleaned


def _strip_list(value: list) -> list:
    for item in value:
        if strip_postgres_nul(item) is not item:
            return [strip_postgres_nul(item) for item in value]
    return value


def _strip_tuple(value: tuple) -> tuple:
    for item in value:
        if strip_postgres_nul(item) is not item:
            return tuple(strip_postgres_nul(item) for item in value)
    return value
