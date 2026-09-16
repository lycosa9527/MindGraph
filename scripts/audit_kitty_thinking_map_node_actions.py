"""Live Kitty node actions on ten real Thinking Maps from Postgres.

Does not write back to Postgres. Structural apply is captured at the Bus.

  LIVE_LLM=1 PYTHONPATH=. python -u scripts/audit_kitty_thinking_map_node_actions.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram.thinking_map_patterns import (
    is_any_thinking_map_leftover_id,
    reserved_ids_for,
    topic_node_id_for,
)
from services.diagram_edit.types import ToolResult
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.agent_loop.tools import dispatch_loop_tool as real_dispatch_loop_tool
from services.kitty.agent_loop.tools import leftover_live_key
from services.kitty.infra.bootstrap.kitty_context_hydrate import diagram_data_from_saved_spec
from services.kitty.routing.outcomes import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from services.utils.error_types import LLM_PIPELINE_ERRORS, REDIS_ERRORS
from tests.kitty_agent_loop_catalog import STRUCTURAL_ACTIONS
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv
from tests.typing_helpers import mock_await_args

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "tmp" / "kitty_thinking_map_node_action_audit.json"

THINKING_MAP_TYPES = (
    "circle_map",
    "bubble_map",
    "double_bubble_map",
    "tree_map",
    "brace_map",
    "flow_map",
    "multi_flow_map",
    "bridge_map",
)

NODE_ACTIONS = ("add_node", "update_node", "update_center", "delete_node")


def _load_env() -> None:
    mindmap_smoke_helpers_load_dotenv(ROOT / ".env")


def _database_url() -> str:
    raw = (os.environ.get("DATABASE_MIGRATION_URL") or os.environ.get("DATABASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL / DATABASE_MIGRATION_URL not set")
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw[len("postgresql://") :]
    if raw.startswith("postgres://"):
        return "postgresql+psycopg://" + raw[len("postgres://") :]
    return raw


async def fetch_pg_thinking_maps(per_type: int) -> List[Dict[str, Any]]:
    """Recent canvas-shaped Thinking Maps, a few of each type."""
    engine = create_async_engine(_database_url(), pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    rows: List[Dict[str, Any]] = []
    try:
        async with factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, title, diagram_type, spec, updated_at
                    FROM (
                      SELECT id, title, diagram_type, spec, updated_at,
                             ROW_NUMBER() OVER (
                               PARTITION BY diagram_type
                               ORDER BY
                                 CASE WHEN title IN ('新图示', '新括号图') THEN 1 ELSE 0 END,
                                 updated_at DESC NULLS LAST
                             ) AS rn
                      FROM diagrams
                      WHERE is_deleted = false
                        AND diagram_type = ANY(:types)
                        AND spec IS NOT NULL
                        AND jsonb_typeof(spec) = 'object'
                        AND jsonb_typeof(spec->'nodes') = 'array'
                        AND jsonb_array_length(spec->'nodes') >= 3
                    ) ranked
                    WHERE rn <= :per_type
                    ORDER BY diagram_type, updated_at DESC NULLS LAST
                    """
                ),
                {"types": list(THINKING_MAP_TYPES), "per_type": per_type},
            )
            for row in result.mappings().all():
                spec = row["spec"]
                if isinstance(spec, str):
                    spec = json.loads(spec)
                if not isinstance(spec, dict):
                    continue
                rows.append(
                    {
                        "id": str(row["id"]),
                        "title": str(row["title"] or ""),
                        "diagram_type": str(row["diagram_type"] or ""),
                        "updated_at": str(row["updated_at"] or ""),
                        "spec": spec,
                    }
                )
    finally:
        await engine.dispose()
    return rows


def _node_text(node: Dict[str, Any]) -> str:
    raw = node.get("text")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    data = node.get("data")
    if isinstance(data, dict):
        label = data.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
    return ""


def _first_live_child(live: Dict[str, Any], diagram_type: str) -> Tuple[str, str]:
    reserved = set(reserved_ids_for(diagram_type))
    reserved.update({"outer-boundary", "dimension-label", "right-topic"})
    topic_id = topic_node_id_for(diagram_type)
    nodes = [node for node in (live.get("nodes") or []) if isinstance(node, dict)]
    by_id = {str(node.get("id")): node for node in nodes if isinstance(node.get("id"), str)}
    child_ids: List[str] = []
    for conn in live.get("connections") or []:
        if not isinstance(conn, dict) or conn.get("source") != topic_id:
            continue
        target = conn.get("target")
        if isinstance(target, str) and target.strip() and target not in reserved:
            child_ids.append(target.strip())
    for node_id in child_ids:
        node = by_id.get(node_id)
        if not node:
            continue
        label = _node_text(node)
        if label and not is_any_thinking_map_leftover_id(node_id):
            return node_id, label
    for node in nodes:
        node_id = str(node.get("id") or "")
        if not node_id or node_id in reserved or is_any_thinking_map_leftover_id(node_id):
            continue
        label = _node_text(node)
        if label:
            return node_id, label
    raise AssertionError(f"{diagram_type} has no live named child")


def hydrate_map(row: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    """Hydrate a library spec into Kitty session context."""
    diagram_type = row["diagram_type"]
    title = str(row.get("title") or "").strip() or "untitled"
    safe = "".join(ch if ch.isalnum() else "_" for ch in title)[:20].strip("_")
    slug = f"{index:02d}_{diagram_type[:6]}_{safe or 'map'}"
    try:
        live = diagram_data_from_saved_spec(row["spec"], diagram_type)
        node_id, label = _first_live_child(live, diagram_type)
    except AssertionError:
        return None
    topic = ""
    for node in live.get("nodes") or []:
        if isinstance(node, dict) and node.get("id") == topic_node_id_for(diagram_type):
            topic = _node_text(node)
            break
    if not topic:
        topic = title
    context = {
        "interaction_language": "zh",
        "one_sentence_phase": "edit",
        "active_panel": "one_sentence",
        "diagram_type": diagram_type,
        "diagram_library_id": row["id"],
        "diagram_data": live,
    }
    return {
        "slug": slug,
        "title": title,
        "diagram_type": diagram_type,
        "topic": topic,
        "branch_label": label,
        "branch_id": node_id,
        "context": context,
        "row_id": row["id"],
    }


def pick_ten(hydrated: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One of each type, then fill to ten with extras."""
    by_type: Dict[str, List[Dict[str, Any]]] = {slug: [] for slug in THINKING_MAP_TYPES}
    for item in hydrated:
        by_type[item["diagram_type"]].append(item)
    picked: List[Dict[str, Any]] = []
    for slug in THINKING_MAP_TYPES:
        if by_type[slug]:
            picked.append(by_type[slug].pop(0))
    while len(picked) < 10:
        progressed = False
        for slug in THINKING_MAP_TYPES:
            if len(picked) >= 10:
                break
            if by_type[slug]:
                picked.append(by_type[slug].pop(0))
                progressed = True
        if not progressed:
            break
    return picked[:10]


def utterance_for(mmap: Dict[str, Any], action: str) -> str:
    """Chinese phrase Kitty should treat as one structural node action."""
    label = mmap["branch_label"]
    topic = mmap["topic"]
    if action == "add_node":
        return _add_utterance(mmap["diagram_type"])
    if action == "update_node":
        return f"把{label}改成要点提纲"
    if action == "update_center":
        return f"主题改成{topic}导学"
    if action == "delete_node":
        return f"删除{label}这个节点"
    raise AssertionError(action)


def _add_utterance(diagram_type: str) -> str:
    """Named add that also says the role this Thinking Map needs."""
    phrases = {
        "circle_map": "添加一个叫冰淇淋的背景",
        "bubble_map": "添加一个叫冰淇淋的特征",
        "double_bubble_map": "添加一个左边不同点冰淇淋",
        "tree_map": "添加一个叫冰淇淋的类别",
        "brace_map": "添加一个叫冰淇淋的部分",
        "flow_map": "添加一个叫冰淇淋的步骤",
        "multi_flow_map": "添加一个叫冰淇淋的原因",
        "bridge_map": "添加一对类比 冰淇淋 和 雪糕",
    }
    return phrases.get(diagram_type, "添加一个叫冰淇淋的节点")


def _applied(action: str, node_id: Optional[str]) -> DiagramCommandResult:
    applied_ops = [{"op": action, "node_id": node_id}] if node_id else [{"op": action}]
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="applied",
            mutation_id="tm-audit",
            revision=2,
            applied_ops=applied_ops,
        ),
        hub_revision=2,
    )


def _first_tool_name(recorded: List[Dict[str, Any]]) -> str:
    for row in recorded:
        calls = row.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            continue
        first = calls[0]
        if not isinstance(first, dict):
            continue
        fn = first.get("function")
        if isinstance(fn, dict) and isinstance(fn.get("name"), str):
            return fn["name"]
    return ""


def leftover_probe(mmap: Dict[str, Any]) -> List[str]:
    """Unmapped leftover slot ids must stay rejected as live keys."""
    errors: List[str] = []
    leftover = leftover_live_key(
        {"action": "update_node", "node_id": "context-0"},
        mmap["context"],
    )
    if leftover != "context-0" and leftover is not None:
        errors.append(f"leftover_key={leftover}")
    if leftover is None and is_any_thinking_map_leftover_id("context-0"):
        # Aliased leftover is allowed; unmapped leftover must reject.
        aliases_ok = any(
            str((node.get("data") or {}).get("circleMapLegacyId") or "") == "context-0"
            for node in mmap["context"]["diagram_data"].get("nodes") or []
            if isinstance(node, dict)
        )
        if not aliases_ok and mmap["diagram_type"] == "circle_map":
            errors.append("leftover_not_rejected")
    if is_any_thinking_map_leftover_id(mmap["branch_id"]):
        errors.append("live_id_is_leftover")
    return errors


def _ok_structural(mmap: Dict[str, Any], action: str, command: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if command.get("action") != action:
        errors.append(f"action={command.get('action')}")
    if action in {"update_node", "delete_node"}:
        node_id = str(command.get("node_id") or "")
        if node_id != mmap["branch_id"]:
            errors.append(f"node_id={node_id} want={mmap['branch_id']}")
        if is_any_thinking_map_leftover_id(node_id):
            errors.append("leftover_id")
    if action == "add_node":
        added = str(command.get("target") or command.get("text") or "")
        if "冰淇淋" not in added:
            errors.append(f"add_target={added}")
    if action == "update_center":
        target = str(command.get("target") or command.get("new_text") or "")
        if "导学" not in target and mmap["topic"] not in target:
            errors.append(f"center={target}")
    return errors


async def run_one(mmap: Dict[str, Any], action: str) -> Dict[str, Any]:
    """One live Kitty action on a fresh session."""
    utterance = utterance_for(mmap, action)
    ws = MagicMock()
    vid = create_voice_session(
        user_id="tm-audit",
        diagram_session_id=f"scope-{mmap['slug']}-{action}",
        diagram_type=mmap["diagram_type"],
    )
    voice_sessions[vid]["context"] = mmap["context"]
    voice_sessions[vid]["active_panel"] = "one_sentence"
    bus_mock = AsyncMock(side_effect=lambda *_a, **_k: _applied(action, mmap["branch_id"]))
    recorded: List[Dict[str, Any]] = []
    llm_ms = 0.0
    errors: List[str] = []
    real_chat = llm_service.chat_raw

    async def _chat(*args: Any, **kwargs: Any) -> Any:
        nonlocal llm_ms
        kwargs["timeout"] = 30.0
        started = time.perf_counter()
        result = await real_chat(*args, **kwargs)
        llm_ms += (time.perf_counter() - started) * 1000.0
        if isinstance(result, dict):
            recorded.append(result)
        return result

    async def _dispatch(
        websocket: Any,
        voice_session_id: str,
        *,
        name: str,
        arguments_json: str,
        session_context: Dict[str, Any],
        diagram_type: str,
        command_text: str,
        verify_required: bool,
    ) -> Any:
        return await real_dispatch_loop_tool(
            websocket,
            voice_session_id,
            name=name,
            arguments_json=arguments_json,
            session_context=session_context,
            diagram_type=diagram_type,
            command_text=command_text,
            verify_required=verify_required,
        )

    started = time.perf_counter()
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", new=_chat),
            patch("services.kitty.agent_loop.loop.dispatch_loop_tool", new=_dispatch),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.interrupt_kitty_tts", new=AsyncMock()),
            patch("services.kitty.agent_loop.loop.load_kitty_live_context", new=AsyncMock(return_value=None)),
            patch(
                "services.kitty.agent_loop.loop.throttled_refresh_voice_context_from_library",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.agent_loop.loop.live_spec_newer_than_library",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "services.kitty.agent_loop.loop.fanout_voice_phase_from_session",
                new=AsyncMock(),
            ),
        ):
            result = await run_typed_agent_loop(ws, vid, utterance, dict(mmap["context"]))
        total_ms = (time.perf_counter() - started) * 1000.0
        command: Dict[str, Any] = {}
        if result.outcome != RouteOutcome.EXECUTED:
            errors.append(f"outcome={result.outcome}")
        if result.reason == "thinking_coins":
            errors.append("thinking_coins")
        if action in STRUCTURAL_ACTIONS:
            if not bus_mock.await_count:
                errors.append("bus_not_called")
            else:
                command = dict(mock_await_args(bus_mock)[2])
                errors.extend(_ok_structural(mmap, action, command))
            if result.reason not in {"fast_structural", "await_canvas"}:
                errors.append(f"reason={result.reason}")
            if result.action != action:
                errors.append(f"loop_action={result.action}")
        return {
            "slug": mmap["slug"],
            "diagram_type": mmap["diagram_type"],
            "topic": mmap["topic"],
            "branch": mmap["branch_label"],
            "branch_id": mmap["branch_id"],
            "action": action,
            "utterance": utterance,
            "ok": not errors,
            "errors": errors,
            "outcome": str(result.outcome),
            "reason": str(result.reason or ""),
            "loop_action": str(result.action or ""),
            "tool": _first_tool_name(recorded),
            "command_action": str(command.get("action") or ""),
            "command_node_id": str(command.get("node_id") or ""),
            "command_target": str(command.get("target") or command.get("text") or "")[:40],
            "llm_ms": round(llm_ms, 1),
            "total_ms": round(total_ms, 1),
            "llm_calls": len(recorded),
        }
    except (*LLM_PIPELINE_ERRORS, AssertionError) as exc:
        return {
            "slug": mmap["slug"],
            "diagram_type": mmap["diagram_type"],
            "topic": mmap["topic"],
            "branch": mmap["branch_label"],
            "branch_id": mmap["branch_id"],
            "action": action,
            "utterance": utterance,
            "ok": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "outcome": "error",
            "reason": "",
            "loop_action": "",
            "tool": "",
            "command_action": "",
            "command_node_id": "",
            "command_target": "",
            "llm_ms": round(llm_ms, 1),
            "total_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "llm_calls": len(recorded),
        }
    finally:
        voice_sessions.pop(vid, None)


def _print_maps(maps: List[Dict[str, Any]]) -> None:
    print("\nPostgres Thinking Maps")
    print(f"{'slug':<32} {'type':<18} {'topic':<18} {'target':<16}")
    for mmap in maps:
        print(
            f"{mmap['slug'][:31]:<32} {mmap['diagram_type']:<18} "
            f"{mmap['topic'][:17]:<18} {mmap['branch_label'][:15]:<16}"
        )


async def _async_main() -> int:
    _load_env()
    rows = await fetch_pg_thinking_maps(per_type=3)
    hydrated = [item for item in (hydrate_map(row, index) for index, row in enumerate(rows, start=1)) if item]
    maps = pick_ten(hydrated)
    if len(maps) < 10:
        print(f"Need 10 hydratable Thinking Maps, got {len(maps)} from {len(rows)} rows")
        return 2
    _print_maps(maps)
    leftover_errors = []
    for mmap in maps:
        leftover_errors.extend(leftover_probe(mmap))
    if leftover_errors:
        print(f"Leftover identity probes: {leftover_errors}")
    else:
        print("Leftover identity probes: all live ids are UUIDs / reserved roots")

    if not live_llm_enabled():
        print("Set LIVE_LLM=1 and a real QWEN_API_KEY")
        return 2
    try:
        init_redis_sync()
    except REDIS_ERRORS as exc:
        print(f"Redis init skipped: {exc}")
    llm_service.initialize()
    print("LLM: live qwen")

    cases: List[Dict[str, Any]] = []
    for mmap in maps:
        for action in NODE_ACTIONS:
            result = await run_one(mmap, action)
            cases.append(result)
            flag = "PASS" if result["ok"] else "FAIL"
            print(
                f"[{flag}] {mmap['diagram_type']}/{action} "
                f"reason={result['reason']} id={result['command_node_id'][:8]} "
                f"{result['total_ms']:.0f}ms"
            )
            if result["errors"]:
                print(f"    {result['errors']}")

    passed = sum(1 for row in cases if row["ok"])
    report = {
        "maps": [
            {
                "id": mmap["row_id"],
                "title": mmap["title"],
                "slug": mmap["slug"],
                "diagram_type": mmap["diagram_type"],
                "topic": mmap["topic"],
                "branch": mmap["branch_label"],
                "branch_id": mmap["branch_id"],
            }
            for mmap in maps
        ],
        "leftover_probe_errors": leftover_errors,
        "passed": passed,
        "failed": len(cases) - passed,
        "cases": cases,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{passed}/{len(cases)} passed  wrote {OUT_JSON}")
    return 0 if passed == len(cases) and not leftover_errors else 1


def main() -> int:
    """CLI entry."""
    argparse.ArgumentParser(description=__doc__).parse_args()
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
