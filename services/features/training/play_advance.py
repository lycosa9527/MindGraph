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


def resolve_play_cursor(
    steps: list[dict[str, Any]],
    index: int,
    live_step: dict[str, Any] | None,
    delta: int,
) -> tuple[int, int]:
    """Return (step_index, mark_step) after a prev/next click."""
    last = max(len(steps) - 1, 0)
    at = min(last, max(0, index))
    live = live_step if isinstance(live_step, dict) else (steps[at] if steps else {})
    current, highest = mark_span(live)
    if delta > 0:
        if current < highest:
            return at, current + 1
        nxt = min(last, at + 1)
        return nxt, 1 if nxt != at else current
    if current > 1:
        return at, current - 1
    prev = max(0, at - 1)
    if prev == at:
        return at, current
    _, prev_high = mark_span(steps[prev])
    return prev, prev_high


def _as_int(value: Any, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    return int(value)
