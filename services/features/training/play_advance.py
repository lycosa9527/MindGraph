"""Resolve prev/next across course slides and in-slide mark builds."""

from __future__ import annotations

from typing import Any


def mark_span(step: dict[str, Any]) -> tuple[int, int]:
    """Current mark click and how many clicks the slide has."""
    current = _as_int(step.get("mark_step"), 1)
    highest = _as_int(step.get("mark_steps"), 1)
    overlays = step.get("overlays") or []
    if isinstance(overlays, list):
        for overlay in overlays:
            if not isinstance(overlay, dict):
                continue
            raw = overlay.get("step")
            if isinstance(raw, (int, float)):
                highest = max(highest, int(raw))
    highest = min(8, max(1, highest))
    current = min(highest, max(1, current))
    return current, highest


def _saved_order(step: dict[str, Any]) -> list[str]:
    """Committed guided-reading node ids. Empty when the slide is not playing one."""
    interact = step.get("interact")
    if not isinstance(interact, dict):
        return []
    if interact.get("mode") != "read" or interact.get("sequence_saved") is not True:
        return []
    raw = interact.get("read_order")
    if not isinstance(raw, list):
        return []
    order: list[str] = []
    for item in raw:
        if isinstance(item, str) and item and item not in order:
            order.append(item)
        if len(order) >= 40:
            break
    return order


def _play_index(step: dict[str, Any], count: int) -> int:
    if count <= 0:
        return 0
    interact = step.get("interact")
    raw = interact.get("play_index") if isinstance(interact, dict) else None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 0
    return min(count - 1, max(0, int(raw)))


def resolve_play_cursor(
    steps: list[dict[str, Any]],
    index: int,
    live_step: dict[str, Any] | None,
    delta: int,
) -> tuple[int, int, int | None]:
    """Return (step_index, mark_step, read_index) after a prev/next click.

    read_index is the guided-reading position when that slide plays an order
    list, and None when the click only moves marks or slides.
    """
    last = max(len(steps) - 1, 0)
    at = min(last, max(0, index))
    live = live_step if isinstance(live_step, dict) else (steps[at] if steps else {})
    if not isinstance(live, dict):
        live = {}
    order = _saved_order(live)
    cursor = _play_index(live, len(order)) if order else 0
    current, highest = mark_span(live)
    if delta > 0:
        if current < highest:
            return at, current + 1, cursor if order else None
        if order and cursor < len(order) - 1:
            return at, highest, cursor + 1
        nxt = min(last, at + 1)
        if nxt == at:
            return at, highest, cursor if order else None
        landing = _saved_order(steps[nxt]) if isinstance(steps[nxt], dict) else []
        return nxt, 1, 0 if landing or order else None
    if order and cursor > 0:
        return at, current, cursor - 1
    if current > 1:
        return at, current - 1, 0 if order else None
    prev = max(0, at - 1)
    if prev == at:
        return at, current, cursor if order else None
    _, prev_high = mark_span(steps[prev])
    previous = _saved_order(steps[prev]) if isinstance(steps[prev], dict) else []
    return prev, prev_high, (len(previous) - 1) if previous else None


def _as_int(value: Any, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    return int(value)
