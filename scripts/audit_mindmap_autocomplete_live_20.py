"""
Live mind-map autocomplete audit: 20 topics → real LLM → PNG + report.

Simulates canvas auto-complete (request_type=autocomplete + locked_topic),
checks topic lock / hierarchy, and writes PNGs under tmp/.

Usage (WSL, repo root):
  LIVE_LLM=1 PYTHONPATH=. python scripts/audit_mindmap_autocomplete_live_20.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

from agents.core.workflow import agent_graph_workflow_with_styles
from agents.mind_maps.mind_map_agent import MindMapAgent
from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from services.utils.error_types import LLM_PIPELINE_ERRORS
from tests.smoke.mindmap_smoke_helpers import (
    live_llm_enabled,
    mindmap_smoke_helpers_load_dotenv,
    mindmap_spec_to_canvas,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "mindmap_autocomplete_live_20"

AUDIT_TOPICS: tuple[tuple[str, str], ...] = (
    ("钢琴", "zh"),
    ("北京三日游计划", "zh"),
    ("光合作用", "zh"),
    ("水循环", "zh"),
    ("二次函数", "zh"),
    ("抗日战争", "zh"),
    ("细胞结构", "zh"),
    ("丝绸之路", "zh"),
    ("牛顿第一定律", "zh"),
    ("唐诗三百首", "zh"),
    ("Photosynthesis", "en"),
    ("Water Cycle", "en"),
    ("Quadratic Functions", "en"),
    ("Ancient Rome", "en"),
    ("Climate Change", "en"),
    ("The Solar System", "en"),
    ("Democracy", "en"),
    ("Machine Learning Basics", "en"),
    ("World War II", "en"),
    ("Healthy Eating", "en"),
)


def _slug(topic: str, index: int) -> str:
    """Filesystem-safe name for a topic."""
    ascii_part = re.sub(r"[^\w\-]+", "_", topic, flags=re.UNICODE).strip("_")
    if not ascii_part or not re.search(r"[A-Za-z0-9]", ascii_part):
        ascii_part = f"topic_{index:02d}"
    return f"{index:02d}_{ascii_part[:48]}"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in (
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "DejaVuSans.ttf",
        "arial.ttf",
    ):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_bubble(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text_value: str,
    *,
    fill: Tuple[int, int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    label = text_value[:36]
    padding_x, padding_y = 14, 9
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


def render_spec_png(spec: Dict[str, Any], path: Path) -> Path:
    """Render topic/children (or canvas nodes) to PNG for audit viewing."""
    canvas = mindmap_spec_to_canvas(spec)
    nodes = canvas.get("nodes") or []
    connections = canvas.get("connections") or []
    usable: List[Tuple[Dict[str, Any], Tuple[float, float]]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        pos = node.get("position")
        if not isinstance(pos, dict):
            continue
        try:
            usable.append((node, (float(pos["x"]), float(pos["y"]))))
        except (KeyError, TypeError, ValueError):
            continue

    path.parent.mkdir(parents=True, exist_ok=True)
    if not usable:
        topic = str(spec.get("topic") or "?")
        image = Image.new("RGB", (1100, 780), (252, 250, 245))
        draw = ImageDraw.Draw(image)
        _draw_bubble(draw, (550, 390), topic, fill=(255, 214, 102), font=_font(20))
        image.save(path, format="PNG")
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
        return (
            int(pad + (xy[0] - min_x) * scale),
            int(pad + (xy[1] - min_y) * scale),
        )

    id_to_xy = {str(node.get("id")): project(xy) for node, xy in usable}
    image = Image.new("RGB", (canvas_w, canvas_h), (252, 250, 245))
    draw = ImageDraw.Draw(image)
    for conn in connections:
        if not isinstance(conn, dict):
            continue
        source = id_to_xy.get(str(conn.get("source")))
        target = id_to_xy.get(str(conn.get("target")))
        if source and target:
            draw.line([source, target], fill=(90, 90, 90), width=2)

    for node, xy in usable:
        projected = project(xy)
        is_topic = str(node.get("id")) == "topic" or str(node.get("type") or "").lower() == "topic"
        label = str(node.get("text") or "").strip() or "?"
        fill = (255, 214, 102) if is_topic else (173, 216, 230)
        _draw_bubble(draw, projected, label, fill=fill, font=_font(16 if is_topic else 13))

    image.save(path, format="PNG")
    return path


def _branch_stats(spec: Dict[str, Any]) -> Dict[str, Any]:
    raw_children = spec.get("children")
    children: list[Any] = raw_children if isinstance(raw_children, list) else []
    nested_ok = 0
    for child in children:
        if not isinstance(child, dict):
            continue
        nested = child.get("children")
        if isinstance(nested, list) and any(
            isinstance(item, dict) and str(item.get("text") or item.get("label") or "").strip() for item in nested
        ):
            nested_ok += 1
    return {
        "branch_count": len(children),
        "branches_with_nested": nested_ok,
    }


async def _run_one(
    index: int,
    topic: str,
    language: str,
    semaphore: asyncio.Semaphore,
) -> Dict[str, Any]:
    slug = _slug(topic, index)
    started = time.time()
    row: Dict[str, Any] = {
        "index": index,
        "topic": topic,
        "language": language,
        "slug": slug,
        "success": False,
        "topic_locked": False,
        "hierarchy_ok": False,
        "returned_topic": "",
        "error": "",
        "png": "",
        "elapsed_s": 0.0,
    }
    async with semaphore:
        try:
            result = await agent_graph_workflow_with_styles(
                topic,
                language=language,
                forced_diagram_type="mind_map",
                model="qwen",
                request_type="autocomplete",
                locked_topic=topic,
                use_rag=False,
            )
        except LLM_PIPELINE_ERRORS as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["elapsed_s"] = round(time.time() - started, 2)
            return row

    row["elapsed_s"] = round(time.time() - started, 2)
    if not result.get("success"):
        row["error"] = str(result.get("error") or result.get("spec") or "generation failed")
        return row

    spec = result.get("spec")
    if not isinstance(spec, dict):
        row["error"] = "missing spec"
        return row

    returned_topic = str(spec.get("topic") or "").strip()
    row["returned_topic"] = returned_topic
    row["topic_locked"] = returned_topic == topic
    row.update(_branch_stats(spec))

    agent = MindMapAgent(model="qwen")
    hierarchy_ok, hierarchy_msg = agent.validate_output(spec, enforce_hierarchy=True)
    row["hierarchy_ok"] = hierarchy_ok
    row["hierarchy_msg"] = hierarchy_msg
    row["success"] = bool(row["topic_locked"] and hierarchy_ok)

    spec_path = OUT_DIR / f"{slug}.json"
    png_path = OUT_DIR / f"{slug}.png"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    render_spec_png(spec, png_path)
    row["png"] = str(png_path.relative_to(ROOT))
    row["spec_json"] = str(spec_path.relative_to(ROOT))

    if not row["topic_locked"]:
        row["error"] = f"topic drift: expected {topic!r} got {returned_topic!r}"
    elif not hierarchy_ok:
        row["error"] = hierarchy_msg
    return row


async def main() -> int:
    """Run live audit for all topics; write report + PNGs."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    mindmap_smoke_helpers_load_dotenv(ROOT / ".env")
    if not live_llm_enabled():
        print("Set LIVE_LLM=1 and a real QWEN_API_KEY in .env")
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    init_redis_sync()
    llm_service.initialize()
    reset_httpx_clients_for_tests()

    # Keep concurrency modest to avoid DashScope rate limits.
    semaphore = asyncio.Semaphore(3)
    tasks = [
        _run_one(index, topic, language, semaphore) for index, (topic, language) in enumerate(AUDIT_TOPICS, start=1)
    ]
    print(f"Running {len(tasks)} live autocomplete mind-map generations → {OUT_DIR}")
    rows = await asyncio.gather(*tasks)

    passed = sum(1 for row in rows if row.get("success"))
    topic_ok = sum(1 for row in rows if row.get("topic_locked"))
    hierarchy_ok = sum(1 for row in rows if row.get("hierarchy_ok"))
    report = {
        "total": len(rows),
        "passed": passed,
        "topic_locked_ok": topic_ok,
        "hierarchy_ok": hierarchy_ok,
        "out_dir": str(OUT_DIR),
        "results": rows,
    }
    report_path = OUT_DIR / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Simple contact-sheet summary image (list status).
    summary = Image.new("RGB", (900, 40 + 28 * len(rows)), (245, 245, 245))
    draw = ImageDraw.Draw(summary)
    font = _font(14)
    draw.text((20, 10), f"Mindmap live audit: {passed}/{len(rows)} passed", fill=(20, 20, 20), font=font)
    for offset, row in enumerate(rows):
        mark = "OK" if row.get("success") else "FAIL"
        color = (20, 120, 40) if row.get("success") else (160, 40, 40)
        line = (
            f"{row['index']:02d} [{mark}] topic_lock={row.get('topic_locked')} "
            f"hierarchy={row.get('hierarchy_ok')}  {row['topic']}"
        )
        draw.text((20, 36 + offset * 28), line[:110], fill=color, font=font)
    summary_path = OUT_DIR / "summary.png"
    summary.save(summary_path, format="PNG")

    print(f"Done: {passed}/{len(rows)} passed")
    print(f"  topic_locked: {topic_ok}/{len(rows)}")
    print(f"  hierarchy_ok: {hierarchy_ok}/{len(rows)}")
    print(f"  PNGs + report: {OUT_DIR}")
    print(f"  summary: {summary_path}")
    for row in rows:
        status = "PASS" if row.get("success") else "FAIL"
        print(
            f"  [{status}] {row['index']:02d} {row['topic']!r} "
            f"→ topic={row.get('returned_topic')!r} "
            f"branches={row.get('branch_count')} nested={row.get('branches_with_nested')} "
            f"{row.get('error') or ''}"
        )

    reset_httpx_clients_for_tests()
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
