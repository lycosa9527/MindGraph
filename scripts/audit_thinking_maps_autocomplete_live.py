"""
Live Thinking Map autocomplete: 8 types × 5 topics → real LLM specs.

Usage (WSL, repo root):
  LIVE_LLM=1 PYTHONPATH=. python scripts/audit_thinking_maps_autocomplete_live.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from agents.core.workflow import agent_graph_workflow_with_styles
from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from services.utils.error_types import LLM_PIPELINE_ERRORS
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "thinking_maps_autocomplete_live"

RUNS: tuple[tuple[str, str], ...] = (
    ("circle_map", "水循环"),
    ("circle_map", "光合作用"),
    ("circle_map", "北京"),
    ("circle_map", "细胞"),
    ("circle_map", "牛顿第一定律"),
    ("bubble_map", "苹果"),
    ("bubble_map", "大象"),
    ("bubble_map", "太阳"),
    ("bubble_map", "钢琴"),
    ("bubble_map", "长城"),
    ("double_bubble_map", "比较猫和狗"),
    ("double_bubble_map", "比较春天和夏天"),
    ("double_bubble_map", "比较城市和农村"),
    ("double_bubble_map", "比较小学和中学"),
    ("double_bubble_map", "比较汽车和火车"),
    ("tree_map", "动物分类"),
    ("tree_map", "食物种类"),
    ("tree_map", "中国地理"),
    ("tree_map", "人体系统"),
    ("tree_map", "文学体裁"),
    ("brace_map", "水分子的组成"),
    ("brace_map", "电脑的组成"),
    ("brace_map", "学校的组成"),
    ("brace_map", "汽车的组成"),
    ("brace_map", "句子的组成"),
    ("flow_map", "做饭的步骤"),
    ("flow_map", "申请护照的步骤"),
    ("flow_map", "种子发芽的过程"),
    ("flow_map", "水循环的过程"),
    ("flow_map", "光合作用的过程"),
    ("multi_flow_map", "战争的原因和结果"),
    ("multi_flow_map", "污染的原因和结果"),
    ("multi_flow_map", "坚持运动的原因和结果"),
    ("multi_flow_map", "考试的原因和结果"),
    ("multi_flow_map", "森林砍伐的原因和结果"),
    ("bridge_map", "心脏像水泵"),
    ("bridge_map", "大脑像电脑"),
    ("bridge_map", "植物的根像吸管"),
    ("bridge_map", "教师像向导"),
    ("bridge_map", "记忆像存档"),
)


def _slug(diagram_type: str, topic: str, index: int) -> str:
    return f"{index:02d}_{diagram_type}_{topic[:24]}"


async def _run_one(
    index: int,
    diagram_type: str,
    topic: str,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    slug = _slug(diagram_type, topic, index)
    started = time.time()
    row: dict[str, Any] = {
        "index": index,
        "diagram_type": diagram_type,
        "topic": topic,
        "slug": slug,
        "success": False,
        "error": "",
        "elapsed_s": 0.0,
        "spec_json": "",
    }
    async with semaphore:
        try:
            result = await agent_graph_workflow_with_styles(
                topic,
                language="zh",
                forced_diagram_type=diagram_type,
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
    if not isinstance(result, dict) or not result.get("success"):
        row["error"] = str((result or {}).get("error") or "generation failed")
        return row
    spec = result.get("spec")
    if not isinstance(spec, dict):
        row["error"] = "missing spec"
        return row
    spec_path = OUT_DIR / f"{slug}.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    row["success"] = True
    row["spec_json"] = str(spec_path.relative_to(ROOT))
    return row


async def main() -> int:
    """Generate five live autocomplete specs for each Thinking Map."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    mindmap_smoke_helpers_load_dotenv(ROOT / ".env")
    if not live_llm_enabled():
        print("Set LIVE_LLM=1 and a real QWEN_API_KEY in .env")
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    init_redis_sync()
    llm_service.initialize()
    reset_httpx_clients_for_tests()

    semaphore = asyncio.Semaphore(3)
    tasks = [
        _run_one(index, diagram_type, topic, semaphore) for index, (diagram_type, topic) in enumerate(RUNS, start=1)
    ]
    print(f"Running {len(tasks)} live thinking-map autocomplete generations → {OUT_DIR}")
    rows = await asyncio.gather(*tasks)
    passed = sum(1 for row in rows if row.get("success"))
    report = {
        "total": len(rows),
        "passed": passed,
        "out_dir": str(OUT_DIR),
        "results": rows,
    }
    report_path = OUT_DIR / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"passed {passed}/{len(rows)} → {report_path}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
