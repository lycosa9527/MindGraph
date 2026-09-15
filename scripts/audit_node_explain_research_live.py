"""Live sweep: one Postgres mindmap, ten node-explain research sessions.

Does not write back to Postgres. Runs the meaning-facet Responses path.

  PYTHONPATH=. python scripts/audit_node_explain_research_live.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agents.mind_maps.node_explain import get_mind_map_node_explain_generator
from config.settings import config
from services.diagram.mindmap_location import is_leftover_mindmap_branch_id
from services.infrastructure.http.error_handler import LLMServiceError
from services.kitty.infra.bootstrap.kitty_context_hydrate import diagram_data_from_saved_spec
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, LLM_PIPELINE_ERRORS
from tests.smoke.mindmap_smoke_helpers import mindmap_smoke_helpers_load_dotenv
from utils.placeholder import is_placeholder_text

ROOT = Path(__file__).resolve().parents[1]
_RUN_ERRORS = (*BACKGROUND_INFRA_ERRORS, *LLM_PIPELINE_ERRORS, LLMServiceError)


def _database_url() -> str:
    raw = (os.environ.get("DATABASE_MIGRATION_URL") or os.environ.get("DATABASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL / DATABASE_MIGRATION_URL not set")
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw[len("postgresql://") :]
    if raw.startswith("postgres://"):
        return "postgresql+psycopg://" + raw[len("postgres://") :]
    return raw


def _safe_host(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or parsed.path or "(unset)"


async def fetch_one_mindmap(
    *,
    diagram_id: str = "",
    exclude_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Most recently updated canvas mindmap with enough named nodes."""
    skipped = {item.strip() for item in (exclude_ids or []) if item and item.strip()}
    wanted = diagram_id.strip()
    engine = create_async_engine(_database_url(), pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, title, diagram_type, spec, language, updated_at
                    FROM diagrams
                    WHERE is_deleted = false
                      AND diagram_type IN ('mind_map', 'mindmap')
                      AND spec IS NOT NULL
                      AND jsonb_typeof(spec) = 'object'
                      AND jsonb_typeof(spec->'nodes') = 'array'
                      AND jsonb_array_length(spec->'nodes') >= 12
                      AND jsonb_typeof(spec->'connections') = 'array'
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT 24
                    """
                )
            )
            for row in result.mappings().all():
                row_id = str(row["id"])
                if wanted and row_id != wanted:
                    continue
                if row_id in skipped:
                    continue
                spec = row["spec"]
                if isinstance(spec, str):
                    spec = json.loads(spec)
                if not isinstance(spec, dict):
                    continue
                return {
                    "id": row_id,
                    "title": str(row["title"] or ""),
                    "diagram_type": str(row["diagram_type"] or "mindmap"),
                    "language": str(row["language"] or "zh"),
                    "updated_at": str(row["updated_at"] or ""),
                    "spec": spec,
                }
    finally:
        await engine.dispose()
    raise RuntimeError("No suitable mindmap found in Postgres")


def _node_label(node: Dict[str, Any]) -> str:
    """Return the display text for a canvas node."""
    label_text = node.get("text")
    if isinstance(label_text, str) and label_text.strip():
        return label_text.strip()
    data = node.get("data")
    if isinstance(data, dict):
        label = data.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
    return ""


def _children(parent_id: str, connections: List[Dict[str, Any]]) -> List[str]:
    """Child node ids under ``parent_id``."""
    kids: List[str] = []
    for conn in connections:
        if conn.get("source") == parent_id:
            target = conn.get("target")
            if isinstance(target, str) and target:
                kids.append(target)
    return kids


def _parent(node_id: str, connections: List[Dict[str, Any]]) -> Optional[str]:
    """Parent node id, if any."""
    for conn in connections:
        if conn.get("target") == node_id:
            source = conn.get("source")
            if isinstance(source, str) and source:
                return source
    return None


def _labels_for(ids: List[str], by_id: Dict[str, Dict[str, Any]]) -> List[str]:
    """Unique non-placeholder labels for the given ids."""
    seen: set[str] = set()
    labels: List[str] = []
    for node_id in ids:
        node = by_id.get(node_id)
        if not node:
            continue
        label = _node_label(node)
        if not label or is_placeholder_text(label) or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels[:16]


def explain_context(
    node_id: str,
    by_id: Dict[str, Dict[str, Any]],
    connections: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Build the same explain payload fields the canvas sends."""
    node = by_id.get(node_id)
    if not node:
        return None
    label = _node_label(node)
    if not label or is_placeholder_text(label):
        return None
    topic_node = by_id.get("topic")
    topic = _node_label(topic_node) if topic_node else label
    if node_id == "topic":
        topic = label
    ancestors: List[str] = []
    current = _parent(node_id, connections) if node_id != "topic" else None
    while current and current != "topic":
        ancestor = by_id.get(current)
        ancestor_label = _node_label(ancestor) if ancestor else ""
        if ancestor_label and not is_placeholder_text(ancestor_label):
            ancestors.insert(0, ancestor_label)
        current = _parent(current, connections)
    parent_id = None if node_id == "topic" else _parent(node_id, connections)
    siblings = (
        []
        if parent_id is None
        else _labels_for([kid for kid in _children(parent_id, connections) if kid != node_id], by_id)
    )
    top = _labels_for(_children("topic", connections), by_id)
    children = top if node_id == "topic" else _labels_for(_children(node_id, connections), by_id)
    return {
        "node_id": node_id,
        "node_label": label,
        "topic": topic,
        "top_level_branches": top,
        "ancestor_path": ancestors,
        "sibling_branches": siblings,
        "child_branches": children,
    }


def pick_ten_nodes(diagram_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """BFS from topic; skip leftover invented ids and placeholder labels."""
    raw_nodes = diagram_data.get("nodes")
    raw_conns = diagram_data.get("connections")
    nodes = [n for n in raw_nodes if isinstance(n, dict)] if isinstance(raw_nodes, list) else []
    connections = [c for c in raw_conns if isinstance(c, dict)] if isinstance(raw_conns, list) else []
    by_id = {str(n.get("id")): n for n in nodes if isinstance(n.get("id"), str)}
    queue = ["topic"] if "topic" in by_id else []
    seen_ids: set[str] = set()
    picked: List[Dict[str, Any]] = []
    seen_labels: set[str] = set()
    while queue and len(picked) < 10:
        node_id = queue.pop(0)
        if node_id in seen_ids:
            continue
        seen_ids.add(node_id)
        queue.extend(kid for kid in _children(node_id, connections) if kid not in seen_ids)
        if node_id != "topic" and is_leftover_mindmap_branch_id(node_id):
            continue
        ctx = explain_context(node_id, by_id, connections)
        if ctx is None or ctx["node_label"] in seen_labels:
            continue
        seen_labels.add(ctx["node_label"])
        picked.append(ctx)
    if len(picked) < 10:
        raise RuntimeError(f"Mindmap only has {len(picked)} usable named nodes")
    return picked


async def run_one(ctx: Dict[str, Any], language: str) -> Dict[str, Any]:
    """Stream one meaning-facet explain and capture timings."""
    generator = get_mind_map_node_explain_generator()
    started = time.perf_counter()
    first_event_at: Optional[float] = None
    first_token_at: Optional[float] = None
    counts: Dict[str, int] = {
        "status": 0,
        "search_source": 0,
        "extract": 0,
        "image": 0,
        "thinking": 0,
        "token": 0,
        "end": 0,
        "error": 0,
    }
    sources = 0
    images = 0
    text_parts: List[str] = []
    last_error = ""
    try:
        async for event in generator.stream_explain(
            node_label=ctx["node_label"],
            topic=ctx["topic"],
            diagram_type="mindmap",
            top_level_branches=ctx["top_level_branches"],
            ancestor_path=ctx["ancestor_path"],
            sibling_branches=ctx["sibling_branches"],
            child_branches=ctx["child_branches"],
            language=language,
            facet="meaning",
            audience_level="general",
        ):
            now = time.perf_counter()
            if first_event_at is None:
                first_event_at = now
            kind = str(event.get("event") or "")
            if kind in counts:
                counts[kind] += 1
            if kind == "token":
                if first_token_at is None:
                    first_token_at = now
                piece = event.get("text")
                if isinstance(piece, str):
                    text_parts.append(piece)
            if kind == "search_source":
                raw = event.get("sources")
                if isinstance(raw, list):
                    sources += len(raw)
            if kind == "image":
                raw = event.get("images")
                if isinstance(raw, list):
                    images += len(raw)
            if kind == "error":
                message = event.get("message")
                last_error = message if isinstance(message, str) else "error"
                break
    except _RUN_ERRORS as exc:
        last_error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    gloss = "".join(text_parts).strip()
    used_research = counts["status"] + counts["search_source"] + counts["extract"] + counts["image"] > 0
    ok = bool(gloss) and counts["error"] == 0 and not last_error
    return {
        "node": ctx["node_label"],
        "ok": ok,
        "research": used_research,
        "fallback_chat": bool(gloss) and not used_research,
        "first_event_s": None if first_event_at is None else round(first_event_at - started, 2),
        "first_token_s": None if first_token_at is None else round(first_token_at - started, 2),
        "total_s": round(elapsed, 2),
        "sources": sources,
        "images": images,
        "events": counts,
        "gloss_chars": len(gloss),
        "gloss": gloss[:80],
        "error": last_error,
    }


def _print_row(index: int, row: Dict[str, Any]) -> None:
    """Print one session line."""
    status = "OK" if row["ok"] else "FAIL"
    path = "research" if row["research"] else ("chat-fallback" if row["fallback_chat"] else "none")
    print(
        f"[{index:02d}] {status:4} {row['total_s']:6.1f}s  "
        f"first_evt={row['first_event_s']}  first_tok={row['first_token_s']}  "
        f"{path:13} src={row['sources']} img={row['images']}  "
        f"{row['node']}",
        flush=True,
    )
    if row["gloss"]:
        print(f"     gloss: {row['gloss']}", flush=True)
    if row["error"]:
        print(f"     error: {row['error']}", flush=True)


async def async_main(
    limit: int,
    start: int,
    diagram_id: str,
    exclude_ids: List[str],
) -> int:
    """Fetch one map, run ``limit`` explain sessions, print timings."""
    row = await fetch_one_mindmap(diagram_id=diagram_id, exclude_ids=exclude_ids)
    live = diagram_data_from_saved_spec(row["spec"], "mindmap")
    targets = pick_ten_nodes(live)[start - 1 : start - 1 + limit]
    language = "zh" if (row.get("language") or "zh").lower().startswith("zh") else "en"
    print(f"map: {row['title'] or row['id']}", flush=True)
    print(f"id:  {row['id']}  updated={row['updated_at']}", flush=True)
    print(f"model: {config.QWEN_MODEL_NODE_EXPLAIN}  host={_safe_host(config.QWEN_RESPONSES_URL)}", flush=True)
    print(f"nodes: {len(targets)}  start={start}  language={language}", flush=True)
    print("-" * 72, flush=True)
    results: List[Dict[str, Any]] = []
    wall = time.perf_counter()
    session_timeout = 180.0
    for index, ctx in enumerate(targets, start=1):
        print(f"[{index:02d}] starting {ctx['node_label']} …", flush=True)
        try:
            result = await asyncio.wait_for(run_one(ctx, language), timeout=session_timeout)
        except TimeoutError:
            result = {
                "node": ctx["node_label"],
                "ok": False,
                "research": False,
                "fallback_chat": False,
                "first_event_s": None,
                "first_token_s": None,
                "total_s": session_timeout,
                "sources": 0,
                "images": 0,
                "events": {},
                "gloss_chars": 0,
                "gloss": "",
                "error": f"session_wall_timeout_{int(session_timeout)}s",
            }
        results.append(result)
        _print_row(index, result)
    wall_s = time.perf_counter() - wall
    ok_n = sum(1 for item in results if item["ok"])
    research_n = sum(1 for item in results if item["research"])
    fallback_n = sum(1 for item in results if item["fallback_chat"])
    totals = [item["total_s"] for item in results]
    firsts = [item["first_token_s"] for item in results if item["first_token_s"] is not None]
    print("-" * 72, flush=True)
    print(
        f"result: {ok_n}/{len(results)} ok  research={research_n}  chat-fallback={fallback_n}  wall={wall_s:.1f}s",
        flush=True,
    )
    if totals:
        print(
            f"timing: min={min(totals):.1f}s  "
            f"median={sorted(totals)[len(totals) // 2]:.1f}s  "
            f"max={max(totals):.1f}s  "
            f"sum={sum(totals):.1f}s",
            flush=True,
        )
    if firsts:
        print(
            f"first token: min={min(firsts):.1f}s  "
            f"median={sorted(firsts)[len(firsts) // 2]:.1f}s  "
            f"max={max(firsts):.1f}s",
            flush=True,
        )
    return 0 if ok_n == len(results) else 1


def main() -> int:
    """Load env, then run the sweep."""
    mindmap_smoke_helpers_load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Live node-explain research sweep")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--start", type=int, default=1, help="1-based node index to start from")
    parser.add_argument("--diagram-id", default="", help="Use this diagram instead of the newest")
    parser.add_argument(
        "--exclude-id",
        action="append",
        default=[],
        help="Skip this diagram id when picking the newest (repeatable)",
    )
    args = parser.parse_args()
    return asyncio.run(
        async_main(
            max(1, args.limit),
            max(1, args.start),
            args.diagram_id,
            list(args.exclude_id),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
