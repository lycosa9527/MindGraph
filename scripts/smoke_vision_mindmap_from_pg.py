"""Pull real mind maps from Postgres, render to PNG, time vision detect/rebuild.

Uses production-shaped settings: ``enable_thinking=false`` and (by default)
``qwen3.6-flash``. Library specs are mostly ``nodes`` + ``connections``.

Usage (WSL, repo root, conda python313):
  PYTHONPATH=. python scripts/smoke_vision_mindmap_from_pg.py --limit 20
  PYTHONPATH=. python scripts/smoke_vision_mindmap_from_pg.py --limit 20 --with-combined
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agents.core.agent_utils import extract_json_from_response
from config.database import DATABASE_MIGRATION_URL, DATABASE_URL
from config.settings import config
from prompts import get_prompt
from services.knowledge.document_ocr import parse_dashscope_multimodal_text
from services.knowledge.vision_mindmap import (
    parse_vision_mindmap_payload,
    sanitize_mindmap_spec,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "handdrawn_mindmap_smoke" / "from_pg"

DETECT_ONLY_PROMPT = (
    'Look at this image. Reply ONLY JSON: {"is_mindmap": true|false, "confidence": 0.0-1.0, "reason": "short"}.'
)

REBUILD_ONLY_PROMPT = (
    "This image is a mind map. Rebuild the exact visible hierarchy. "
    "Reply ONLY JSON: "
    '{"topic":"...","children":[{"id":"...","text":"...","children":[...]}]}.'
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Best-effort TTF font."""
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _node_label(node: Dict[str, Any]) -> str:
    """Extract display text from a mind-map node."""
    data = node.get("data")
    if isinstance(data, dict):
        nested = data.get("text") or data.get("label")
        if nested:
            return str(nested).strip()[:40]
    return str(node.get("text") or node.get("label") or "").strip()[:40] or "?"


def _node_xy(node: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Read canvas position from a Pinia-style node."""
    position = node.get("position")
    if not isinstance(position, dict):
        return None
    try:
        return float(position["x"]), float(position["y"])
    except (KeyError, TypeError, ValueError):
        return None


def render_mindmap_png(spec: Dict[str, Any], path: Path) -> Path:
    """Render a PNG from library ``nodes``/``connections`` (or topic/children)."""
    nodes = spec.get("nodes")
    connections = spec.get("connections")
    if isinstance(nodes, list) and nodes:
        return _render_from_nodes(nodes, connections if isinstance(connections, list) else [], path)
    return _render_from_topic_children(spec, path)


def _render_from_nodes(
    nodes: List[Any],
    connections: List[Any],
    path: Path,
) -> Path:
    """Draw the saved canvas layout into a fixed-size PNG."""
    usable: List[Tuple[Dict[str, Any], Tuple[float, float]]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        xy = _node_xy(node)
        if xy is None:
            continue
        usable.append((node, xy))
    if not usable:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1100, 780), (252, 250, 245)).save(path, format="PNG")
        return path

    xs = [xy[0] for _, xy in usable]
    ys = [xy[1] for _, xy in usable]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    pad = 80
    canvas_w, canvas_h = 1100, 780
    scale = min((canvas_w - 2 * pad) / span_x, (canvas_h - 2 * pad) / span_y)

    def project(xy: Tuple[float, float]) -> Tuple[int, int]:
        x = int(pad + (xy[0] - min_x) * scale)
        y = int(pad + (xy[1] - min_y) * scale)
        return x, y

    id_to_xy = {str(node.get("id")): project(xy) for node, xy in usable}
    image = Image.new("RGB", (canvas_w, canvas_h), (252, 250, 245))
    draw = ImageDraw.Draw(image)
    node_font = _font(14)
    title_font = _font(18)

    for conn in connections:
        if not isinstance(conn, dict):
            continue
        source = id_to_xy.get(str(conn.get("source")))
        target = id_to_xy.get(str(conn.get("target")))
        if source and target:
            draw.line([source, target], fill=(90, 90, 90), width=2)

    for node, xy in usable:
        projected = project(xy)
        is_topic = str(node.get("type") or "").lower() in {"topic", "root"} or str(node.get("id")) == "topic"
        fill = (255, 214, 102) if is_topic else (173, 216, 230)
        font = title_font if is_topic else node_font
        _draw_bubble(draw, projected, _node_label(node), fill=fill, font=font)

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path


def _draw_bubble(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text_value: str,
    *,
    fill: Tuple[int, int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    """Draw a labeled oval at ``xy``."""
    label = text_value[:28]
    padding_x, padding_y = 12, 8
    bbox = draw.textbbox((0, 0), label, font=font)
    width = int(bbox[2] - bbox[0]) + padding_x * 2
    height = int(bbox[3] - bbox[1]) + padding_y * 2
    left, top = xy[0] - width // 2, xy[1] - height // 2
    draw.ellipse(
        (left, top, left + width, top + height),
        fill=fill,
        outline=(50, 50, 50),
        width=2,
    )
    draw.text(xy, label, fill=(20, 20, 20), font=font, anchor="mm")


def _render_from_topic_children(spec: Dict[str, Any], path: Path) -> Path:
    """Fallback radial layout for legacy topic/children specs."""
    topic = str(spec.get("topic") or "Mind Map").strip() or "Mind Map"
    children = spec.get("children")
    if not isinstance(children, list):
        children = []
    image = Image.new("RGB", (1100, 780), (252, 250, 245))
    draw = ImageDraw.Draw(image)
    center = (550, 390)
    _draw_bubble(draw, center, topic, fill=(255, 214, 102), font=_font(20))

    count = max(len(children), 1)
    for index, child in enumerate(children[:12]):
        if not isinstance(child, dict):
            continue
        angle = -math.pi / 2 + (2 * math.pi * index / count)
        branch_xy = (int(center[0] + 250 * math.cos(angle)), int(center[1] + 250 * math.sin(angle)))
        draw.line([center, branch_xy], fill=(90, 90, 90), width=3)
        _draw_bubble(draw, branch_xy, _node_label(child), fill=(173, 216, 230), font=_font(14))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path


def _parse_json_object(raw: str) -> Dict[str, Any]:
    """Parse model JSON, including fenced / partial responses."""
    text_value = (raw or "").strip()
    if not text_value:
        return {}
    try:
        parsed = json.loads(text_value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        extracted = extract_json_from_response(text_value, allow_partial=True)
        return extracted if isinstance(extracted, dict) else {}


def _dashscope_timed(
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    *,
    model: str,
    timeout_sec: float = 180.0,
) -> Tuple[float, str, Dict[str, Any]]:
    """One multimodal call; returns (seconds, raw text, usage)."""
    api_key = config.QWEN_API_KEY
    if not api_key:
        raise ValueError("QWEN_API_KEY missing")
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:{mime_type};base64,{image_b64}"},
                        {"text": prompt},
                    ],
                }
            ]
        },
        "parameters": {
            "enable_thinking": False,
        },
    }
    url = f"{config.DASHSCOPE_API_URL}services/aigc/multimodal-generation/generation"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    started = time.perf_counter()
    with httpx.Client(timeout=timeout_sec) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
    elapsed = time.perf_counter() - started
    usage = result.get("usage") if isinstance(result, dict) else {}
    if not isinstance(usage, dict):
        usage = {}
    return elapsed, parse_dashscope_multimodal_text(result), usage


async def _fetch_mindmaps(limit: int) -> List[Dict[str, Any]]:
    """Load distinct recent mind maps that have a canvas ``nodes`` array."""
    database_url = DATABASE_MIGRATION_URL or DATABASE_URL
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    rows: List[Dict[str, Any]] = []
    try:
        async with session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, user_id, title, diagram_type, spec, language
                    FROM (
                      SELECT id, user_id, title, diagram_type, spec, language,
                             updated_at,
                             ROW_NUMBER() OVER (
                               PARTITION BY title
                               ORDER BY updated_at DESC NULLS LAST
                             ) AS rn
                      FROM diagrams
                      WHERE is_deleted = false
                        AND diagram_type IN ('mind_map', 'mindmap')
                        AND spec IS NOT NULL
                        AND jsonb_typeof(spec) = 'object'
                        AND jsonb_typeof(spec->'nodes') = 'array'
                        AND jsonb_array_length(spec->'nodes') >= 3
                    ) ranked
                    WHERE rn = 1
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            fetched = list(result.mappings().all())
            for row in fetched:
                spec = row["spec"]
                if isinstance(spec, str):
                    spec = json.loads(spec)
                if not isinstance(spec, dict):
                    continue
                rows.append(
                    {
                        "id": str(row["id"]),
                        "user_id": int(row["user_id"]),
                        "title": str(row["title"] or ""),
                        "language": str(row["language"] or "zh"),
                        "spec": spec,
                    }
                )
    finally:
        await engine.dispose()
    return rows


def _count_nodes(spec: Optional[Dict[str, Any]]) -> int:
    """Count visible nodes in a library or rebuilt spec."""
    if not spec:
        return 0
    nodes = spec.get("nodes")
    if isinstance(nodes, list):
        return len(nodes)

    def walk(items: Any) -> int:
        if not isinstance(items, list):
            return 0
        total = 0
        for node in items:
            if not isinstance(node, dict):
                continue
            total += 1
            total += walk(node.get("children"))
        return total

    if spec.get("topic"):
        return 1 + walk(spec.get("children"))
    return walk(spec.get("children"))


def _avg(values: List[float]) -> float:
    """Mean of a non-empty list."""
    return sum(values) / len(values) if values else 0.0


async def _run(limit: int, model: str, with_combined: bool) -> int:
    """Fetch PG mind maps, render, time detect vs rebuild."""
    print(f"Vision model: {model}")
    print("enable_thinking: False")
    print(f"Fetching up to {limit} distinct mind maps from Postgres...")
    rows = await _fetch_mindmaps(limit)
    if not rows:
        print("No mind maps with nodes[] found.")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Loaded {len(rows)} diagram(s). Output: {OUT}")

    detect_times: List[float] = []
    rebuild_times: List[float] = []
    combined_times: List[float] = []
    detect_ok = 0
    rebuild_ok = 0

    for index, row in enumerate(rows, start=1):
        title = (row["title"] or row["id"])[:60]
        png_path = OUT / f"{index:02d}_{row['id'][:8]}.png"
        render_mindmap_png(row["spec"], png_path)
        image_bytes = png_path.read_bytes()
        src_nodes = _count_nodes(row["spec"])
        print(f"\n=== [{index}/{len(rows)}] {title} ===")
        print(f"diagram_id={row['id']} source_nodes≈{src_nodes} png={png_path.name}")

        is_mm = True
        try:
            detect_s, detect_raw, detect_usage = _dashscope_timed(
                image_bytes,
                "image/png",
                DETECT_ONLY_PROMPT,
                model=model,
            )
            detect_json = _parse_json_object(detect_raw)
            is_mm = bool(detect_json.get("is_mindmap"))
            conf = float(detect_json.get("confidence") or 0.0)
            reason = str(detect_json.get("reason") or "")[:120]
            print(
                f"detect:  {detect_s:6.2f}s  is_mindmap={is_mm} "
                f"confidence={conf:.2f} reason={reason!r} "
                f"out_tokens={detect_usage.get('output_tokens')}"
            )
            detect_times.append(detect_s)
            if is_mm:
                detect_ok += 1
        except httpx.HTTPError as exc:
            print(f"detect:  FAILED {exc}")

        if is_mm:
            try:
                rebuild_s, rebuild_raw, rebuild_usage = _dashscope_timed(
                    image_bytes,
                    "image/png",
                    REBUILD_ONLY_PROMPT,
                    model=model,
                )
                rebuilt = sanitize_mindmap_spec(_parse_json_object(rebuild_raw))
                rebuilt_nodes = _count_nodes(rebuilt)
                topic = (rebuilt or {}).get("topic", "")
                print(
                    f"rebuild: {rebuild_s:6.2f}s  nodes≈{rebuilt_nodes} "
                    f"topic={topic!r} out_tokens={rebuild_usage.get('output_tokens')}"
                )
                rebuild_times.append(rebuild_s)
                if rebuilt_nodes > 0:
                    rebuild_ok += 1
            except httpx.HTTPError as exc:
                print(f"rebuild: FAILED {exc}")
        else:
            print("rebuild: skipped (not detected as mind map)")

        if with_combined:
            try:
                system_prompt = get_prompt(
                    "mind_map",
                    row["language"] or "zh",
                    "vision_handdrawn",
                )
                combined_s, combined_raw, combined_usage = _dashscope_timed(
                    image_bytes,
                    "image/png",
                    system_prompt + "\n\nDetect whether this image is a mind map / concept map and, "
                    "if yes, rebuild the exact hierarchy as JSON.",
                    model=model,
                )
                combined = parse_vision_mindmap_payload(combined_raw)
                print(
                    f"combined: {combined_s:6.2f}s  is_mindmap={combined.is_mindmap} "
                    f"nodes≈{_count_nodes(combined.spec)} conf={combined.confidence:.2f} "
                    f"out_tokens={combined_usage.get('output_tokens')}"
                )
                combined_times.append(combined_s)
            except httpx.HTTPError as exc:
                print(f"combined: FAILED {exc}")

    print("\n========== SUMMARY ==========")
    print(f"samples: {len(rows)}")
    print(f"detect success (is_mindmap=true): {detect_ok}/{len(detect_times)}")
    print(f"rebuild success (nodes>0):      {rebuild_ok}/{len(rebuild_times)}")
    if detect_times:
        print(f"detect avg:  {_avg(detect_times):6.2f}s  (min {min(detect_times):.2f} / max {max(detect_times):.2f})")
    if rebuild_times:
        print(
            f"rebuild avg: {_avg(rebuild_times):6.2f}s  (min {min(rebuild_times):.2f} / max {max(rebuild_times):.2f})"
        )
    if detect_times and rebuild_times:
        print(f"detect+rebuild sum avg: {_avg(detect_times) + _avg(rebuild_times):6.2f}s")
    if combined_times:
        print(
            f"combined avg: {_avg(combined_times):6.2f}s  "
            f"(min {min(combined_times):.2f} / max {max(combined_times):.2f})"
        )
    return 0


def main() -> int:
    """CLI entry."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20, help="How many distinct mind maps")
    parser.add_argument(
        "--model",
        default="qwen3.6-flash",
        help="DashScope vision model (default: qwen3.6-flash)",
    )
    parser.add_argument(
        "--with-combined",
        action="store_true",
        help="Also time the production combined detect+rebuild call",
    )
    args = parser.parse_args()
    model = (args.model or "").strip() or "qwen3.6-flash"
    return asyncio.run(_run(max(1, min(args.limit, 50)), model=model, with_combined=bool(args.with_combined)))


if __name__ == "__main__":
    raise SystemExit(main())
