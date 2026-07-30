"""
Live canvas auto-complete audit via the exact HTTP SSE pipeline.

Calls ``POST /api/generate_graph/stream`` (same path as
``useAutoComplete.generateFromSingleLLM``) with:

  prompt, diagram_type=mindmap, language, request_type=autocomplete,
  locked_topic, llm=qwen

Writes PNG + JSON + report under tmp/mindmap_autocomplete_stream_20/.

Usage (WSL, repo root):
  LIVE_LLM=1 PYTHONPATH=. python scripts/audit_mindmap_autocomplete_stream_20.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from httpx import ASGITransport
from PIL import Image, ImageDraw, ImageFont

from agents.mind_maps.mind_map_agent import MindMapAgent
from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from main import app
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from tests.smoke.mindmap_smoke_helpers import (
    live_llm_enabled,
    mindmap_smoke_helpers_load_dotenv,
    mindmap_spec_to_canvas,
)
from utils.auth.authentication import get_current_user_or_api_key

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "mindmap_autocomplete_stream_20"
STREAM_PATH = "/api/generate_graph/stream"

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
    """Filesystem-safe name; keep CJK when present."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", topic).strip().strip(".")
    if not cleaned:
        cleaned = f"topic_{index:02d}"
    return f"{index:02d}_{cleaned[:48]}"


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
    """Render mind-map spec to PNG for audit viewing."""
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
    image = Image.new("RGB", (1100, 780), (252, 250, 245))
    draw = ImageDraw.Draw(image)
    if not usable:
        topic = str(spec.get("topic") or "?")
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
    scale = min((1100 - 2 * pad) / span_x, (780 - 2 * pad) / span_y)

    def project(xy: Tuple[float, float]) -> Tuple[int, int]:
        return (
            int(pad + (xy[0] - min_x) * scale),
            int(pad + (xy[1] - min_y) * scale),
        )

    id_to_xy = {str(node.get("id")): project(xy) for node, xy in usable}
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
    return {"branch_count": len(children), "branches_with_nested": nested_ok}


def _parse_sse_complete(raw_text: str) -> Optional[Dict[str, Any]]:
    """Extract the final complete/error event from an SSE response body."""
    complete: Optional[Dict[str, Any]] = None
    for block in raw_text.split("\n\n"):
        line = block.strip()
        if not line.startswith("data:"):
            continue
        payload_text = line[len("data:") :].strip()
        if not payload_text:
            continue
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        event = payload.get("event")
        if event in ("complete", "error"):
            complete = payload
    return complete


async def _call_stream(
    client: httpx.AsyncClient,
    topic: str,
    language: str,
) -> Dict[str, Any]:
    """POST the canvas auto-complete SSE body and return the complete payload."""
    # Match useAutoComplete.requestBody + llm model field.
    body = {
        "prompt": topic,
        "diagram_type": "mindmap",
        "language": language,
        "request_type": "autocomplete",
        "locked_topic": topic,
        "llm": "qwen",
    }
    response = await client.post(STREAM_PATH, json=body, timeout=180.0)
    if response.status_code != 200:
        return {
            "success": False,
            "error": f"HTTP {response.status_code}: {response.text[:300]}",
            "endpoint": STREAM_PATH,
        }
    payload = _parse_sse_complete(response.text)
    if payload is None:
        return {
            "success": False,
            "error": "SSE stream ended without complete/error event",
            "endpoint": STREAM_PATH,
        }
    payload["endpoint"] = STREAM_PATH
    payload["http_status"] = response.status_code
    return payload


async def _run_one(
    client: httpx.AsyncClient,
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
        "endpoint": STREAM_PATH,
        "success": False,
        "topic_locked": False,
        "hierarchy_ok": False,
        "returned_topic": "",
        "error": "",
        "png": "",
        "elapsed_s": 0.0,
        "phases_ok": False,
    }
    async with semaphore:
        payload = await _call_stream(client, topic, language)
    row["elapsed_s"] = round(time.time() - started, 2)

    if payload.get("event") == "error" or not payload.get("success"):
        row["error"] = str(payload.get("message") or payload.get("error") or payload.get("error_type") or "failed")
        return row

    spec = payload.get("spec")
    if not isinstance(spec, dict):
        row["error"] = "complete event missing spec"
        return row

    returned_topic = str(spec.get("topic") or "").strip()
    row["returned_topic"] = returned_topic
    row["topic_locked"] = returned_topic == topic
    row.update(_branch_stats(spec))
    row["diagram_type"] = payload.get("diagram_type")
    row["request_id"] = payload.get("request_id")
    row["llm_model"] = payload.get("llm_model")

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


async def _noop_user() -> None:
    """Auth override: stream endpoint allows Optional[User]=None after Depends."""
    return None


async def main() -> int:
    """Run SSE canvas auto-complete audit for all topics."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    mindmap_smoke_helpers_load_dotenv(ROOT / ".env")
    if not live_llm_enabled():
        print("Set LIVE_LLM=1 and a real QWEN_API_KEY in .env")
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    init_redis_sync()
    llm_service.initialize()
    reset_httpx_clients_for_tests()

    app.dependency_overrides[get_current_user_or_api_key] = _noop_user
    transport = ASGITransport(app=app)
    semaphore = asyncio.Semaphore(3)

    print(f"Canvas SSE audit → {STREAM_PATH} → {OUT_DIR}")
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            tasks = [
                _run_one(client, index, topic, language, semaphore)
                for index, (topic, language) in enumerate(AUDIT_TOPICS, start=1)
            ]
            rows = await asyncio.gather(*tasks)
    finally:
        app.dependency_overrides.pop(get_current_user_or_api_key, None)
        reset_httpx_clients_for_tests()

    passed = sum(1 for row in rows if row.get("success"))
    topic_ok = sum(1 for row in rows if row.get("topic_locked"))
    hierarchy_ok = sum(1 for row in rows if row.get("hierarchy_ok"))
    report = {
        "pipeline": "POST /api/generate_graph/stream (canvas auto-complete)",
        "total": len(rows),
        "passed": passed,
        "topic_locked_ok": topic_ok,
        "hierarchy_ok": hierarchy_ok,
        "out_dir": str(OUT_DIR),
        "results": rows,
    }
    (OUT_DIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = Image.new("RGB", (980, 40 + 28 * len(rows)), (245, 245, 245))
    draw = ImageDraw.Draw(summary)
    font = _font(14)
    draw.text(
        (20, 10),
        f"SSE canvas autocomplete: {passed}/{len(rows)} passed  ({STREAM_PATH})",
        fill=(20, 20, 20),
        font=font,
    )
    for offset, row in enumerate(rows):
        mark = "OK" if row.get("success") else "FAIL"
        color = (20, 120, 40) if row.get("success") else (160, 40, 40)
        line = (
            f"{row['index']:02d} [{mark}] topic_lock={row.get('topic_locked')} "
            f"hierarchy={row.get('hierarchy_ok')}  {row['topic']}"
        )
        draw.text((20, 36 + offset * 28), line[:120], fill=color, font=font)
    summary_path = OUT_DIR / "summary.png"
    summary.save(summary_path, format="PNG")

    print(f"Done: {passed}/{len(rows)} passed via {STREAM_PATH}")
    print(f"  topic_locked: {topic_ok}/{len(rows)}")
    print(f"  hierarchy_ok: {hierarchy_ok}/{len(rows)}")
    print(f"  output: {OUT_DIR}")
    for row in rows:
        status = "PASS" if row.get("success") else "FAIL"
        print(
            f"  [{status}] {row['index']:02d} {row['topic']!r} "
            f"→ topic={row.get('returned_topic')!r} "
            f"branches={row.get('branch_count')} nested={row.get('branches_with_nested')} "
            f"{row.get('error') or ''}"
        )
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
