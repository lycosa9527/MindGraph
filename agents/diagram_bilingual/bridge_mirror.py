"""Keep bridge-map glosses when an agent rebuilds the spec from pieces.

A complete mirror stays on ``secondary`` and goes through the usual peel.
A partial mirror is stored on the analogy objects so one missing line does
not drop every translation.
"""

from __future__ import annotations

from typing import Any


def _gloss(record: Any, *keys: str) -> str:
    if not isinstance(record, dict):
        return ""
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _mirror(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    raw = result.get("secondary")
    if isinstance(raw, dict):
        return raw
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def bridge_has_inline_gloss(spec: dict[str, Any]) -> bool:
    """True when a rebuilt bridge spec kept glosses outside ``secondary``."""
    if _gloss(spec, "dimension_secondary"):
        return True
    if _string_list(spec.get("alternative_dimensions_secondary")):
        return True
    analogies = spec.get("analogies")
    if not isinstance(analogies, list):
        return False
    return any(_gloss(item, "left_secondary", "right_secondary") for item in analogies if isinstance(item, dict))


def _pair_glosses(
    analogies: list[Any],
    existing: list[dict[str, Any]],
    new_pairs: list[Any],
) -> list[tuple[str, str]] | None:
    rows: list[tuple[str, str]] = []
    for index, item in enumerate(analogies):
        if not isinstance(item, dict):
            return None
        if index < len(existing):
            rows.append(
                (
                    _gloss(existing[index], "left_secondary", "leftSecondary"),
                    _gloss(existing[index], "right_secondary", "rightSecondary"),
                )
            )
            continue
        offset = index - len(existing)
        gloss_pair = new_pairs[offset] if offset < len(new_pairs) else None
        rows.append((_gloss(gloss_pair, "left"), _gloss(gloss_pair, "right")))
    return rows


def _dimension_gloss(existing: list[dict[str, Any]], mirror: dict[str, Any] | None) -> str:
    for pair in existing:
        gloss = _gloss(pair, "dimension_secondary", "dimensionSecondary")
        if gloss:
            return gloss
    if mirror is None:
        return ""
    return _gloss(mirror, "dimension")


def _mirror_complete(
    spec: dict[str, Any],
    rows: list[tuple[str, str]],
    dimension_gloss: str,
    alternatives: list[str],
) -> bool:
    analogies = spec.get("analogies")
    if not isinstance(analogies, list) or len(analogies) != len(rows):
        return False
    for item, (left, right) in zip(analogies, rows):
        if not isinstance(item, dict):
            return False
        if _gloss(item, "left") and not left:
            return False
        if _gloss(item, "right") and not right:
            return False
    if _gloss(spec, "dimension") and not dimension_gloss:
        return False
    primary_alts = spec.get("alternative_dimensions")
    if isinstance(primary_alts, list) and primary_alts and len(alternatives) < len(primary_alts):
        return False
    return True


def _write_partial(
    spec: dict[str, Any],
    analogies: list[Any],
    rows: list[tuple[str, str]],
    dimension_gloss: str,
    alternatives: list[str],
) -> None:
    if dimension_gloss:
        spec["dimension_secondary"] = dimension_gloss
    if alternatives:
        spec["alternative_dimensions_secondary"] = alternatives
    for item, (left, right) in zip(analogies, rows):
        if not isinstance(item, dict):
            continue
        if left:
            item["left_secondary"] = left
        if right:
            item["right_secondary"] = right


def stamp_bridge_bilingual(
    spec: dict[str, Any],
    llm_result: dict[str, Any] | None,
    existing_pairs: list[Any] | None = None,
) -> None:
    """Copy canvas glosses and the model mirror onto a rebuilt bridge spec."""
    analogies = spec.get("analogies")
    if not isinstance(analogies, list) or not analogies:
        return
    existing = [pair for pair in (existing_pairs or []) if isinstance(pair, dict)]
    mirror = _mirror(llm_result)
    new_pairs = mirror.get("analogies") if isinstance(mirror, dict) else None
    if not isinstance(new_pairs, list):
        new_pairs = []
    rows = _pair_glosses(analogies, existing, new_pairs)
    if rows is None:
        return
    dimension_gloss = _dimension_gloss(existing, mirror)
    alternatives = _string_list(mirror.get("alternative_dimensions") if isinstance(mirror, dict) else None)
    if not _mirror_complete(spec, rows, dimension_gloss, alternatives):
        _write_partial(spec, analogies, rows, dimension_gloss, alternatives)
        return
    primary_alts = spec.get("alternative_dimensions")
    alt_count = len(primary_alts) if isinstance(primary_alts, list) else 0
    relating = spec.get("relating_factor")
    spec["secondary"] = {
        "relating_factor": relating if isinstance(relating, str) else "as",
        "dimension": dimension_gloss,
        "analogies": [{"left": left, "right": right} for left, right in rows],
        "alternative_dimensions": alternatives[:alt_count],
    }
