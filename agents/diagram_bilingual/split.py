"""Keep or drop the sibling ``secondary`` object on a generated spec.

A bad mirror is removed. The primary spec is left for the existing validators.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _string_ok(primary: str, secondary: Any) -> bool:
    if not isinstance(secondary, str):
        return False
    if primary.strip() and not secondary.strip():
        return False
    return True


# Agent-owned strings. They are not a second language line, so a missing
# mirror copies the primary value instead of dropping the whole translation.
_COPIED_KEYS = frozenset({"id", "relating_factor"})


def mirror_matches(primary: Any, secondary: Any) -> bool:
    """True when ``secondary`` copies the string structure of ``primary``."""
    return mirror_mismatch_reason(primary, secondary) is None


def mirror_mismatch_reason(primary: Any, secondary: Any, path: str = "") -> str | None:
    """Short path of the first structural mismatch, or None when the mirror fits."""
    if isinstance(primary, str):
        if _string_ok(primary, secondary):
            return None
        return path or "value"
    if isinstance(primary, list):
        if not isinstance(secondary, list) or len(primary) != len(secondary):
            return path or "list"
        for index, item in enumerate(primary):
            reason = mirror_mismatch_reason(item, secondary[index], f"{path}[{index}]")
            if reason:
                return reason
        return None
    if isinstance(primary, dict):
        if not isinstance(secondary, dict):
            return path or "object"
        for key, value in primary.items():
            if key == "secondary" or key.startswith("_"):
                continue
            if not isinstance(value, (str, list, dict)):
                continue
            child_path = f"{path}.{key}" if path else key
            if key not in secondary:
                return child_path
            reason = mirror_mismatch_reason(value, secondary[key], child_path)
            if reason:
                return reason
        return None
    return None


def _fit_value(primary: Any, secondary: Any) -> Any | None:
    if isinstance(primary, str):
        if not _string_ok(primary, secondary):
            return None
        return secondary
    if isinstance(primary, list):
        return _fit_list(primary, secondary)
    if isinstance(primary, dict):
        return _fit_dict(primary, secondary)
    return secondary


def _fit_list(primary: list[Any], secondary: Any) -> list[Any] | None:
    if not isinstance(secondary, list) or len(secondary) < len(primary):
        return None
    fitted: list[Any] = []
    for index, item in enumerate(primary):
        if isinstance(item, (str, list, dict)):
            child = _fit_value(item, secondary[index])
            if child is None:
                return None
            fitted.append(child)
        else:
            fitted.append(secondary[index])
    return fitted


def _fit_dict(primary: dict[str, Any], secondary: Any) -> dict[str, Any] | None:
    if not isinstance(secondary, dict):
        return None
    fitted: dict[str, Any] = {}
    for key, value in primary.items():
        if key == "secondary" or key.startswith("_"):
            continue
        if not isinstance(value, (str, list, dict)):
            continue
        if key not in secondary:
            if key in _COPIED_KEYS and isinstance(value, str):
                fitted[key] = value
                continue
            return None
        child = _fit_value(value, secondary[key])
        if child is None:
            return None
        fitted[key] = child
    return fitted


def tighten_secondary(spec: dict[str, Any]) -> None:
    """Trim a longer mirror down to the primary spec. Leave a bad mirror for peel."""
    raw = spec.get("secondary")
    if not isinstance(raw, dict):
        return
    body = {key: value for key, value in spec.items() if key != "secondary"}
    fitted = _fit_dict(body, raw)
    if fitted is not None:
        spec["secondary"] = fitted


def transplant_secondary(source: dict[str, Any], target: dict[str, Any]) -> None:
    """Copy ``source['secondary']`` onto a spec the agent rebuilt from ``source``."""
    raw = source.get("secondary")
    if isinstance(raw, dict):
        target["secondary"] = raw
    tighten_secondary(target)


def peel_bilingual_spec(spec: dict[str, Any], primary_language: str, secondary_language: str) -> bool:
    """Validate ``spec['secondary']``. Drop it when the mirror does not match.

    Returns True when a usable secondary object remains.
    """
    secondary = spec.get("secondary")
    if not isinstance(secondary, dict):
        spec.pop("secondary", None)
        return False
    reason = mirror_mismatch_reason(spec, secondary)
    if reason:
        logger.warning("Bilingual mirror did not match the primary spec (%s); dropping secondary", reason)
        spec.pop("secondary", None)
        return False
    spec["languages"] = {
        "primary": primary_language,
        "secondary": secondary_language,
    }
    return True
