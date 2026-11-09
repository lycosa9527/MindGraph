"""Regenerate real diagram topics in dual language (zh + en) for the layout audit.

Reads PG-exported fixtures (``{"name", "diagram_type", "spec"}``), takes each
diagram's topic as the prompt, and runs the real generate pipeline with
``secondary_language``. Results land in ``tmp/bilingual_audit/`` where
``frontend/tests/bilingualLayout.audit.spec.ts`` lays them out.

Usage (WSL, repo root, conda python313):
  PYTHONPATH=. python scripts/audit_bilingual_layout_live.py --per-type 3
  PYTHONPATH=. python scripts/audit_bilingual_layout_live.py --only mindmap --per-type 8
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.core.generate_pipeline import run_generate_pipeline
from clients.llm.http_client_manager import reset_httpx_clients_for_tests
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = ROOT / "tmp" / "real_diagrams" / "fixtures"
OUT = ROOT / "tmp" / "bilingual_audit"

PLACEHOLDER_MARKERS = ("点击", "Click", "[", "新节点", "主题")
TOPIC_FIELDS = ("topic", "whole", "event", "main_topic", "title", "central_topic")
TOPIC_NODE_TYPES = ("topic", "center", "main", "title", "root")


def _clean(value: Any) -> str:
    """Return a usable label or an empty string for placeholders."""
    text_value = str(value or "").strip()
    if len(text_value) < 2 or any(marker in text_value for marker in PLACEHOLDER_MARKERS):
        return ""
    return text_value


def _node_text(node: Dict[str, Any]) -> str:
    """Display text of a Pinia-style node."""
    raw_data = node.get("data")
    data: Dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    return _clean(node.get("text") or node.get("label") or data.get("label") or data.get("text"))


def _topic_from_nodes(nodes: List[Dict[str, Any]], diagram_type: str) -> str:
    """Topic node text, or a bridge-map first analogy pair."""
    for node in nodes:
        if node.get("id") == "topic" or node.get("type") in TOPIC_NODE_TYPES:
            label = _node_text(node)
            if label:
                return label
    if diagram_type == "bridge_map":
        pairs = [_node_text(n) for n in nodes if str(n.get("id", "")).startswith("pair-")]
        pairs = [p for p in pairs if p]
        if len(pairs) >= 2:
            return f"{pairs[0]} 与 {pairs[1]} 的类比"
    for node in nodes:
        label = _node_text(node)
        if label:
            return label
    return ""


def extract_prompt(diagram_type: str, spec: Dict[str, Any]) -> str:
    """Best topic prompt for one exported spec."""
    if diagram_type == "double_bubble_map":
        left, right = _clean(spec.get("left")), _clean(spec.get("right"))
        return f"比较{left}和{right}" if left and right else ""
    for field in TOPIC_FIELDS:
        label = _clean(spec.get(field))
        if label:
            return label
    nodes = spec.get("nodes")
    if isinstance(nodes, list):
        return _topic_from_nodes([n for n in nodes if isinstance(n, dict)], diagram_type)
    return ""


def pick_fixtures(fixture_dir: Path, per_type: int, only: Optional[str]) -> List[Dict[str, Any]]:
    """Fixtures with a real topic, at most ``per_type`` per diagram type."""
    picked: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    for path in sorted(fixture_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        diagram_type = str(payload.get("diagram_type") or "")
        if only and only not in diagram_type:
            continue
        if counts.get(diagram_type, 0) >= per_type:
            continue
        spec = payload.get("spec") if isinstance(payload.get("spec"), dict) else {}
        prompt = extract_prompt(diagram_type, spec)
        if not prompt:
            continue
        counts[diagram_type] = counts.get(diagram_type, 0) + 1
        picked.append({"source": path.stem, "diagram_type": diagram_type, "prompt": prompt})
    return picked


async def generate_one(item: Dict[str, Any], model: str, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
    """Run the real pipeline once and save the bilingual spec."""
    forced = "mind_map" if item["diagram_type"] in ("mindmap", "mind_map") else item["diagram_type"]
    async with semaphore:
        started = time.time()
        result = await run_generate_pipeline(
            item["prompt"],
            language="zh",
            secondary_language="en",
            forced_diagram_type=forced,
            model=model,
            request_type="diagram_generation",
        )
        elapsed = time.time() - started
    spec = result.get("spec") if isinstance(result, dict) else None
    ok = isinstance(spec, dict) and not spec.get("error") and bool(spec.get("languages"))
    record = {
        "name": f"{item['source']}-bilingual",
        "source": item["source"],
        "diagram_type": item["diagram_type"],
        "prompt": item["prompt"],
        "seconds": round(elapsed, 1),
        "ok": ok,
        "spec": spec,
    }
    if ok:
        (OUT / f"{record['name']}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


async def main_async(args: argparse.Namespace) -> int:
    """Generate every picked fixture and print a summary."""
    mindmap_smoke_helpers_load_dotenv(ROOT / ".env")
    if not live_llm_enabled():
        print("Set LIVE_LLM=1 and a real QWEN_API_KEY in .env")
        return 2
    init_redis_sync()
    llm_service.initialize()
    reset_httpx_clients_for_tests()
    OUT.mkdir(parents=True, exist_ok=True)
    picked = [] if args.extra_only else pick_fixtures(Path(args.fixtures), args.per_type, args.only)
    for index, extra in enumerate(args.extra or [], start=1):
        diagram_type, _, prompt = extra.partition("=")
        if diagram_type and prompt:
            picked.append(
                {"source": f"{diagram_type}-extra{index:02d}", "diagram_type": diagram_type, "prompt": prompt}
            )
    print(f"picked {len(picked)} fixtures")
    semaphore = asyncio.Semaphore(args.concurrency)
    records = await asyncio.gather(*(generate_one(item, args.model, semaphore) for item in picked))
    failed = 0
    for record in records:
        status = "ok " if record["ok"] else "FAIL"
        failed += 0 if record["ok"] else 1
        print(f"{status} {record['seconds']:>5}s {record['name']:<36} {record['prompt'][:40]}")
    print(f"{len(records) - failed}/{len(records)} bilingual specs written to {OUT}")
    return 1 if failed else 0


def main() -> int:
    """CLI entry."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))
    parser.add_argument("--per-type", type=int, default=3)
    parser.add_argument("--only", default=None, help="Substring of diagram_type to keep")
    parser.add_argument("--model", default="qwen")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument(
        "--extra",
        action="append",
        help="Extra prompt as diagram_type=prompt (repeatable), e.g. double_bubble_map=比较光合作用和呼吸作用",
    )
    parser.add_argument("--extra-only", action="store_true", help="Run only --extra prompts")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
