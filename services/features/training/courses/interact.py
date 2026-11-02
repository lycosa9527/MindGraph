"""Course-slide interaction payload: guided reading, drag-to-build, quiz."""

from __future__ import annotations

from typing import Any

_MODES = frozenset({"read", "drag", "quiz"})
_CHOICE_IDS = ("a", "b", "c")
_EXTRA_KINDS = ("note", "mascot", "video", "image")


def _text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _read_order(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    order: list[str] = []
    for item in raw:
        node_id = _text(item, 80)
        if node_id:
            order.append(node_id)
        if len(order) >= 80:
            break
    return order


def _blanks(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        node_id = _text(item.get("node_id"), 80)
        if not node_id:
            continue
        row = {"node_id": node_id, "answer": _text(item.get("answer"), 200)}
        hint = _text(item.get("hint"), 400)
        if hint:
            row["hint"] = hint
        rows.append(row)
        if len(rows) >= 48:
            break
    return rows


def _choices(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return [{"id": choice_id, "label": "", "correct": False} for choice_id in _CHOICE_IDS]
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw[:3]):
        if not isinstance(item, dict):
            continue
        choice_id = _text(item.get("id"), 8) or _CHOICE_IDS[min(index, 2)]
        rows.append(
            {
                "id": choice_id,
                "label": _text(item.get("label"), 120),
                "correct": bool(item.get("correct")),
            }
        )
    while len(rows) < 3:
        rows.append({"id": _CHOICE_IDS[len(rows)], "label": "", "correct": False})
    return rows


def _quizzes(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in raw[:4]:
        if not isinstance(item, dict):
            continue
        node_id = _text(item.get("node_id"), 80)
        prompt = _text(item.get("prompt"), 300)
        if not node_id and not prompt:
            continue
        rows.append(
            {
                "node_id": node_id,
                "prompt": prompt,
                "choices": _choices(item.get("choices")),
            }
        )
    return rows


def _node_extras(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in raw[:40]:
        if not isinstance(item, dict):
            continue
        node_id = _text(item.get("node_id"), 80)
        if not node_id:
            continue
        kinds_raw = item.get("kinds")
        kinds: list[str] = []
        if isinstance(kinds_raw, list):
            for kind in kinds_raw:
                label = _text(kind, 16)
                if label in _EXTRA_KINDS and label not in kinds:
                    kinds.append(label)
        if kinds:
            row: dict[str, Any] = {"node_id": node_id, "kinds": kinds}
            vod_id = _text(item.get("vod_media_id"), 80)
            if vod_id and "video" in kinds:
                row["vod_media_id"] = vod_id
            rows.append(row)
    return rows


def clean_interact(raw: object) -> dict[str, Any] | None:
    """Drop unknown modes. None means the slide has no interaction."""
    if not isinstance(raw, dict):
        return None
    mode = raw.get("mode")
    if mode not in _MODES:
        return None
    return {
        "mode": mode,
        "read_order": _read_order(raw.get("read_order")),
        "blanks": _blanks(raw.get("blanks")),
        "quizzes": _quizzes(raw.get("quizzes")),
        "sequence_saved": mode in ("read", "drag") and raw.get("sequence_saved") is True,
        "node_extras": _node_extras(raw.get("node_extras")),
    }
