"""
Live review: 5 topics × 7 专业程度 via POST /api/generate_graph/stream.

Writes PNG + JSON + per-topic contact sheets under
tmp/mindmap_audience_review/.

Usage (WSL, repo root):
  LIVE_LLM=1 PYTHONPATH=. python scripts/review_mindmap_audience_levels.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from httpx import ASGITransport
from PIL import Image, ImageDraw, ImageFont

from main import app
from clients.llm.http_client_manager import reset_httpx_clients_for_tests
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
OUT_DIR = ROOT / "tmp" / "mindmap_audience_review"
STREAM_PATH = "/api/generate_graph/stream"

REVIEW_TOPICS: tuple[str, ...] = (
    "光合作用",
    "北京三日游",
    "机器学习",
    "茶叶",
    "通货膨胀",
)

LEVELS: tuple[tuple[str, str], ...] = (
    ("general", "通用"),
    ("primary", "小学"),
    ("junior", "初中"),
    ("senior", "高中"),
    ("university", "大学"),
    ("adult", "成人"),
    ("expert", "专家"),
)

# Keep in sync with frontend/src/composables/mindMap/audience/aiContentLevelInstructions.zh.ts
AUDIENCE_ZH: Dict[str, Optional[str]] = {
    "general": None,
    "primary": (
        "请按「小学」专业程度生成内容。\n"
        "用语：只用日常具体词，禁止术语、抽象概念名和英文缩写。\n"
        "句子：短句；每条宜在十余字内，能朗读给小学生听。\n"
        "前提：只假设生活常识，不假设任何学科基础。\n"
        "深度：能指认、举例、说“是什么”；不要原理、分类框架或因果链。"
    ),
    "junior": (
        "请按「初中」专业程度生成内容。\n"
        "用语：清晰白话；可少量学科词，首次出现用生活说法带过。\n"
        "句子：短到中等，一层意思一句。\n"
        "前提：假设义务教育常识，不假设高中专项。\n"
        "深度：覆盖是什么、简单分类与直接用途；少谈争议与理论模型。"
    ),
    "senior": (
        "请按「高中」专业程度生成内容。\n"
        "用语：可用规范学科用语，少科普铺垫。\n"
        "句子：完整，把概念关系写清楚。\n"
        "前提：假设高中该科常见概念。\n"
        "深度：抽象完整；写清因果、对比与适用条件；不要大学论文腔。"
    ),
    "university": (
        "请按「大学」专业程度生成内容。\n"
        "用语：用学科术语与理论视角，不必解释入门词。\n"
        "句子：按论证组织，可稍长。\n"
        "前提：假设本科通识与该科基础。\n"
        "深度：按学科框架写机制、证据与限度；可点出模型或流派，避免中小学教案口吻。"
    ),
    "adult": (
        "请按「成人」专业程度生成内容。\n"
        "用语：清晰专业，少课堂口吻。\n"
        "句子：直接，面向做事。\n"
        "前提：假设职场常识，不假设学历阶梯。\n"
        "深度：侧重场景、决策与利弊；少定理推导与考试知识点罗列。"
    ),
    "expert": (
        "请按「专家」专业程度生成内容。\n"
        "用语：领域术语，禁止科普开场。\n"
        "句子：密、准、短，去掉过渡句。\n"
        "前提：假设同行背景。\n"
        "深度：写机制、边界、争议与反例；不要定义课、类比故事或教学脚手架。"
    ),
}


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


def render_spec_png(spec: Dict[str, Any], path: Path, banner: str) -> Path:
    """Render mind-map spec to PNG with a level banner."""
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
    banner_h = 42
    image = Image.new("RGB", (1100, 780 + banner_h), (252, 250, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1100, banner_h), fill=(30, 41, 59))
    draw.text((16, 10), banner[:80], fill=(248, 250, 252), font=_font(18))

    if not usable:
        topic = str(spec.get("topic") or "?")
        _draw_bubble(draw, (550, 390 + banner_h), topic, fill=(255, 214, 102), font=_font(20))
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
            int(pad + banner_h + (xy[1] - min_y) * scale),
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


def write_contact_sheet(topic: str, png_paths: List[Path], dest: Path) -> Path:
    """Stack the seven level PNGs for one topic into a single review sheet."""
    tiles: List[Image.Image] = []
    for path in png_paths:
        if path.is_file():
            tiles.append(Image.open(path).convert("RGB"))
        else:
            blank = Image.new("RGB", (1100, 822), (240, 240, 240))
            ImageDraw.Draw(blank).text((24, 24), f"missing {path.name}", fill=(160, 40, 40), font=_font(20))
            tiles.append(blank)
    width = max(tile.width for tile in tiles)
    header_h = 48
    height = header_h + sum(tile.height for tile in tiles)
    sheet = Image.new("RGB", (width, height), (252, 250, 245))
    header = ImageDraw.Draw(sheet)
    header.rectangle((0, 0, width, header_h), fill=(15, 23, 42))
    header.text((16, 12), f"{topic}  ·  7 专业程度", fill=(248, 250, 252), font=_font(22))
    top = header_h
    for tile in tiles:
        sheet.paste(tile, (0, top))
        top += tile.height
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, format="PNG")
    return dest


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
        if isinstance(payload, dict) and payload.get("event") in ("complete", "error"):
            complete = payload
    return complete


async def _call_stream(
    client: httpx.AsyncClient,
    topic: str,
    instructions: Optional[str],
) -> Dict[str, Any]:
    """POST canvas auto-complete SSE with optional 专业程度 instructions."""
    body: Dict[str, Any] = {
        "prompt": topic,
        "diagram_type": "mindmap",
        "language": "zh",
        "request_type": "autocomplete",
        "locked_topic": topic,
        "llm": "qwen",
    }
    if instructions:
        body["generation_instructions"] = instructions
    response = await client.post(STREAM_PATH, json=body, timeout=180.0)
    if response.status_code != 200:
        return {
            "success": False,
            "error": f"HTTP {response.status_code}: {response.text[:300]}",
        }
    payload = _parse_sse_complete(response.text)
    if payload is None:
        return {"success": False, "error": "SSE stream ended without complete/error event"}
    return payload


async def _run_one(
    client: httpx.AsyncClient,
    topic: str,
    level_id: str,
    level_label: str,
    semaphore: asyncio.Semaphore,
) -> Dict[str, Any]:
    started = time.time()
    row: Dict[str, Any] = {
        "topic": topic,
        "level": level_id,
        "level_label": level_label,
        "success": False,
        "error": "",
        "png": "",
        "elapsed_s": 0.0,
        "returned_topic": "",
        "branch_count": 0,
    }
    async with semaphore:
        payload = await _call_stream(client, topic, AUDIENCE_ZH[level_id])
    row["elapsed_s"] = round(time.time() - started, 2)
    if payload.get("event") == "error" or not payload.get("success"):
        row["error"] = str(payload.get("message") or payload.get("error") or "failed")
        return row
    spec = payload.get("spec")
    if not isinstance(spec, dict):
        row["error"] = "complete event missing spec"
        return row
    children = spec.get("children")
    row["returned_topic"] = str(spec.get("topic") or "").strip()
    row["branch_count"] = len(children) if isinstance(children, list) else 0
    row["success"] = True
    topic_dir = OUT_DIR / topic
    spec_path = topic_dir / f"{level_id}.json"
    png_path = topic_dir / f"{level_id}.png"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    render_spec_png(spec, png_path, f"{topic}  ·  {level_label} ({level_id})")
    row["png"] = str(png_path.relative_to(ROOT))
    row["spec_json"] = str(spec_path.relative_to(ROOT))
    return row


async def _noop_user() -> None:
    """Auth override: stream endpoint allows Optional[User]=None after Depends."""
    return None


async def main() -> int:
    """Run live 专业程度 review for five topics."""
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
    jobs = [(topic, level_id, level_label) for topic in REVIEW_TOPICS for level_id, level_label in LEVELS]
    print(f"Audience review → {STREAM_PATH} → {OUT_DIR} ({len(jobs)} maps)")
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            rows = await asyncio.gather(
                *[_run_one(client, topic, level_id, level_label, semaphore) for topic, level_id, level_label in jobs]
            )
    finally:
        app.dependency_overrides.pop(get_current_user_or_api_key, None)
        reset_httpx_clients_for_tests()

    sheets: List[str] = []
    for topic in REVIEW_TOPICS:
        pngs = [OUT_DIR / topic / f"{level_id}.png" for level_id, _ in LEVELS]
        sheet = write_contact_sheet(topic, pngs, OUT_DIR / f"{topic}_all7.png")
        sheets.append(str(sheet.relative_to(ROOT)))

    passed = sum(1 for row in rows if row.get("success"))
    report = {
        "pipeline": "POST /api/generate_graph/stream + generation_instructions",
        "total": len(rows),
        "passed": passed,
        "topics": list(REVIEW_TOPICS),
        "contact_sheets": sheets,
        "out_dir": str(OUT_DIR),
        "results": list(rows),
    }
    (OUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done: {passed}/{len(rows)} via {STREAM_PATH}")
    print(f"  output: {OUT_DIR}")
    for sheet in sheets:
        print(f"  sheet: {sheet}")
    for row in rows:
        status = "PASS" if row.get("success") else "FAIL"
        print(
            f"  [{status}] {row['topic']} / {row['level_label']} "
            f"topic={row.get('returned_topic')!r} branches={row.get('branch_count')} "
            f"{row.get('error') or ''}"
        )
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
