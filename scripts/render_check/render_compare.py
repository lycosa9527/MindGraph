"""Box and screenshot comparison for the headless render check."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, TypedDict, cast

from PIL import Image, ImageChops

MOVE_TOLERANCE_PX = 1.0
PIXEL_DELTA = 24
PIXEL_CHANGE_LIMIT = 0.002


class BoxRow(TypedDict):
    """One painted Vue Flow node (flow coordinates, DOM size)."""

    key: str
    type: str
    x: float | None
    y: float | None
    w: float
    h: float


class PaintBox(TypedDict):
    """Flow position and DOM size of one painted frame."""

    x: float
    y: float
    w: float
    h: float


class TimelineRow(TypedDict):
    """One node from its first painted frame to the frame the layout settled on."""

    id: str
    key: str
    type: str
    first: PaintBox
    last: PaintBox
    moves: int
    fonts_at_first: str


def settled_rows(timeline: list[TimelineRow]) -> list[BoxRow]:
    """Settled boxes keyed by label, comparable across page loads."""
    rows: list[BoxRow] = []
    for row in sorted(timeline, key=lambda item: item["key"]):
        last = row["last"]
        rows.append(
            {"key": row["key"], "type": row["type"], "x": last["x"], "y": last["y"], "w": last["w"], "h": last["h"]}
        )
    return rows


def _differs(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is not b
    return abs(a - b) > MOVE_TOLERANCE_PX


def _box_drift(before: list[BoxRow], after: list[BoxRow]) -> list[str]:
    previous = {row["key"]: row for row in before}
    drift: list[str] = []
    for row in after:
        old = previous.get(row["key"])
        if old is None:
            drift.append(f"{row['key']}: new")
            continue
        for field in ("x", "y", "w", "h"):
            if _differs(cast(float | None, old[field]), cast(float | None, row[field])):
                drift.append(f"{row['key']}.{field}: {old[field]} -> {row[field]}")
    keys = {row["key"] for row in after}
    drift.extend(f"{row['key']}: missing" for row in before if row["key"] not in keys)
    return drift


def describe_jumps(timeline: list[TimelineRow]) -> list[str]:
    """Nodes whose painted box changed after the frame they first appeared in."""
    jumps: list[str] = []
    for row in timeline:
        first, last = row["first"], row["last"]
        for field in ("x", "y", "w", "h"):
            if abs(first[field] - last[field]) > MOVE_TOLERANCE_PX:
                jumps.append(f"{row['key']}.{field}: {first[field]} -> {last[field]} ({row['moves']} moves)")
    return jumps


def _circles_overlap(a: BoxRow, b: BoxRow) -> bool:
    """Discs inscribed in both boxes intersect by more than 1px."""
    ax, ay = cast(float, a["x"]), cast(float, a["y"])
    bx, by = cast(float, b["x"]), cast(float, b["y"])
    dx = (ax + a["w"] / 2) - (bx + b["w"] / 2)
    dy = (ay + a["h"] / 2) - (by + b["h"] / 2)
    radii = min(a["w"], a["h"]) / 2 + min(b["w"], b["h"]) / 2
    return math.hypot(dx, dy) < radii - 1


def count_overlaps(rows: list[BoxRow]) -> int:
    """Pairs of painted nodes overlapping by more than 1px; two circle nodes compare as discs."""
    boxes = [row for row in rows if row["x"] is not None and row["y"] is not None and row["type"] != "boundary"]
    count = 0
    for index, a in enumerate(boxes):
        ax, ay = cast(float, a["x"]), cast(float, a["y"])
        for b in boxes[index + 1 :]:
            bx, by = cast(float, b["x"]), cast(float, b["y"])
            ix = min(ax + a["w"], bx + b["w"]) - max(ax, bx)
            iy = min(ay + a["h"], by + b["h"]) - max(ay, by)
            if ix <= 1 or iy <= 1:
                continue
            if a["type"] == "circle" and b["type"] == "circle" and not _circles_overlap(a, b):
                continue
            count += 1
    return count


def pixel_change_ratio(before: Path, after: Path) -> float:
    """Share of pixels whose channel difference exceeds PIXEL_DELTA (1.0 if sizes differ)."""
    with Image.open(before) as image_a, Image.open(after) as image_b:
        if image_a.size != image_b.size:
            return 1.0
        diff = ImageChops.difference(image_a.convert("RGB"), image_b.convert("RGB")).convert("L")
        changed = sum(1 for value in diff.getdata() if int(cast(int, value)) > PIXEL_DELTA)
        return changed / max(image_a.size[0] * image_a.size[1], 1)


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def compare_runs(before_dir: Path, after_dir: Path) -> list[str]:
    """One line per regression between two labelled runs."""
    regressions: list[str] = []
    for after_file in sorted(after_dir.glob("*.json")):
        before_file = before_dir / after_file.name
        if not before_file.exists():
            continue
        before, after = _load(before_file), _load(after_file)
        name = after_file.stem
        if after.get("error") and not before.get("error"):
            regressions.append(f"{name}: render error {after['error']}")
            continue
        if after.get("error") or before.get("error"):
            continue
        if len(after.get("page_errors", [])) > len(before.get("page_errors", [])):
            regressions.append(f"{name}: new page errors {after['page_errors']}")
        if int(after["overlaps"]) > int(before["overlaps"]):
            regressions.append(f"{name}: overlaps {before['overlaps']} -> {after['overlaps']}")
        if len(after["jumps"]) > len(before["jumps"]):
            regressions.append(f"{name}: jumps after first paint {len(before['jumps'])} -> {len(after['jumps'])}")
        drift = _box_drift(cast(list[BoxRow], before["settled"]), cast(list[BoxRow], after["settled"]))
        if drift:
            regressions.append(f"{name}: settled boxes changed ({len(drift)}) e.g. {drift[:3]}")
        png_a, png_b = before_dir / f"{name}.png", after_dir / f"{name}.png"
        if png_a.exists() and png_b.exists():
            ratio = pixel_change_ratio(png_a, png_b)
            if ratio > PIXEL_CHANGE_LIMIT:
                regressions.append(f"{name}: screenshot changed {ratio:.2%}")
    return regressions
