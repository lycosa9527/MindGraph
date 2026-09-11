"""Audit Kitty node actions on ten Postgres mindmaps (two rounds each).

Does not write back to Postgres. Structural apply is captured at the Bus command;
canvas persist / auto-complete generation are stubbed like the live suite.

  LIVE_LLM=1 PYTHONPATH=. python scripts/audit_kitty_pg_node_actions.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram.mindmap_location import is_leftover_mindmap_branch_id
from services.diagram_edit.types import ToolResult
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.agent_loop.tools import dispatch_loop_tool as real_dispatch_loop_tool
from services.kitty.routing.command_router import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from services.utils.error_types import LLM_PIPELINE_ERRORS, REDIS_ERRORS
from tests.kitty_agent_loop_catalog import (
    NODE_ACTIONS,
    STRUCTURAL_ACTIONS,
    RealMindmap,
    load_real_mindmap_from_spec,
    utterance_for,
)
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv
from tests.typing_helpers import mock_await_args

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "tmp" / "kitty_pg_node_action_audit.json"


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


async def fetch_pg_mindmaps(limit: int) -> List[Dict[str, Any]]:
    """Distinct recent canvas-shaped mindmaps from Postgres."""
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
                        AND jsonb_typeof(spec->'connections') = 'array'
                    ) ranked
                    WHERE rn = 1
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
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
                        "diagram_type": str(row["diagram_type"] or "mindmap"),
                        "updated_at": str(row["updated_at"] or ""),
                        "spec": spec,
                    }
                )
    finally:
        await engine.dispose()
    return rows


def _applied(action: str, node_id: Optional[str]) -> DiagramCommandResult:
    applied_ops = [{"op": action, "node_id": node_id}] if node_id else [{"op": action}]
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="applied",
            mutation_id="pg-audit",
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


def _slug_for(row: Dict[str, Any], index: int) -> str:
    title = str(row.get("title") or "").strip() or "untitled"
    safe = "".join(ch if ch.isalnum() else "_" for ch in title)[:24].strip("_")
    return f"{index:02d}_{safe or 'map'}"


def hydrate_maps(rows: List[Dict[str, Any]]) -> List[tuple[Dict[str, Any], RealMindmap]]:
    """Skip rows that cannot hydrate to a named L1 branch."""
    out: List[tuple[Dict[str, Any], RealMindmap]] = []
    for index, row in enumerate(rows, start=1):
        slug = _slug_for(row, index)
        try:
            mmap = load_real_mindmap_from_spec(slug, row["spec"])
        except AssertionError:
            continue
        mmap.context["diagram_library_id"] = row["id"]
        mmap.context["diagram_type"] = "mindmap"
        out.append((row, mmap))
        if len(out) >= 10:
            break
    return out


def _ok_structural(mmap: RealMindmap, action: str, command: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if command.get("action") != action:
        errors.append(f"action={command.get('action')}")
    if action in {"update_node", "delete_node"}:
        node_id = str(command.get("node_id") or "")
        if node_id != mmap.branch_id:
            errors.append(f"node_id={node_id} want={mmap.branch_id}")
        if is_leftover_mindmap_branch_id(node_id):
            errors.append("leftover_id")
    if action == "add_node" and "扩展阅读" not in str(command.get("target") or ""):
        errors.append(f"add_target={command.get('target')}")
    if action == "update_center":
        target = str(command.get("target") or "")
        if "导学" not in target and mmap.topic not in target:
            errors.append(f"center={target}")
    return errors


async def run_one(
    mmap: RealMindmap,
    action: str,
    round_n: int,
    *,
    use_live_llm: bool,
) -> Dict[str, Any]:
    """One action on a fresh session. Does not persist the library row."""
    utterance = utterance_for(mmap, action)
    ws = MagicMock()
    vid = create_voice_session(
        user_id="pg-audit",
        diagram_session_id=f"scope-{mmap.slug}-{action}-r{round_n}",
        diagram_type="mindmap",
    )
    voice_sessions[vid]["context"] = mmap.context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    bus_mock = AsyncMock(side_effect=lambda *_a, **_k: _applied(action, mmap.branch_id))
    branch_mock = AsyncMock(return_value=True)
    start_ac_mock = AsyncMock(return_value=True)
    ws_mock = AsyncMock(return_value=True)
    recorded: List[Dict[str, Any]] = []
    llm_ms = 0.0
    errors: List[str] = []

    async def _chat(*args: Any, **kwargs: Any) -> Any:
        nonlocal llm_ms
        kwargs["timeout"] = 30.0
        started = time.perf_counter()
        result = await llm_service.chat_raw(*args, **kwargs)
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

    chat_target = _chat if use_live_llm else AsyncMock(side_effect=AssertionError("LLM disabled"))
    started = time.perf_counter()
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", new=chat_target),
            patch("services.kitty.agent_loop.loop.dispatch_loop_tool", new=_dispatch),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.tools.emit_auto_complete_branch", branch_mock),
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                start_ac_mock,
            ),
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", ws_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
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
            result = await run_typed_agent_loop(ws, vid, utterance, dict(mmap.context))
        total_ms = (time.perf_counter() - started) * 1000.0
        tool_name = _first_tool_name(recorded)
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
        elif action == "auto_complete_branch":
            if not branch_mock.await_count:
                errors.append("branch_not_called")
            if tool_name and tool_name != "node_action.auto_complete_branch":
                errors.append(f"tool={tool_name}")
        elif action == "auto_complete":
            if not ws_mock.await_count:
                errors.append("ws_not_called")
            if tool_name and tool_name != "node_action.auto_complete":
                errors.append(f"tool={tool_name}")
        elif action == "clarify_options":
            pending = voice_sessions[vid].get("pending_clarify_options")
            if result.action != "clarify_options" or not isinstance(pending, dict):
                errors.append(f"clarify={result.action}")
        return {
            "slug": mmap.slug,
            "topic": mmap.topic,
            "branch": mmap.branch_label,
            "branch_id": mmap.branch_id,
            "action": action,
            "round": round_n,
            "utterance": utterance,
            "ok": not errors,
            "errors": errors,
            "outcome": str(result.outcome),
            "reason": str(result.reason or ""),
            "loop_action": str(result.action or ""),
            "tool": tool_name,
            "command_action": str(command.get("action") or ""),
            "command_node_id": str(command.get("node_id") or ""),
            "command_target": str(command.get("target") or "")[:40],
            "llm_ms": round(llm_ms, 1),
            "total_ms": round(total_ms, 1),
            "llm_calls": len(recorded),
        }
    except (*LLM_PIPELINE_ERRORS, AssertionError) as exc:
        return {
            "slug": mmap.slug,
            "topic": mmap.topic,
            "branch": mmap.branch_label,
            "branch_id": mmap.branch_id,
            "action": action,
            "round": round_n,
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


def _print_maps(pairs: List[tuple[Dict[str, Any], RealMindmap]]) -> None:
    print("\nPostgres mindmaps")
    print(f"{'#':<3} {'title':<28} {'topic':<20} {'L1':<16} nodes")
    for row, mmap in pairs:
        nodes = mmap.context.get("diagram_data", {}).get("nodes")
        n_nodes = len(nodes) if isinstance(nodes, list) else 0
        print(f"{mmap.slug:<3} {row['title'][:27]:<28} {mmap.topic[:19]:<20} {mmap.branch_label[:15]:<16} {n_nodes}")


def _print_results(cases: List[Dict[str, Any]]) -> None:
    print("\nNode-action audit (2 rounds)")
    print(f"{'case':<46} {'r':>1} {'ok':<4} {'reason':<16} {'ms':>8}")
    for row in cases:
        case = f"{row['slug']}/{row['action']}"
        flag = "PASS" if row["ok"] else "FAIL"
        print(f"{case:<46} {row['round']:>1} {flag:<4} {row['reason']:<16} {row['total_ms']:8.0f}")
        if row["errors"]:
            print(f"    {row['errors']}")


async def _async_main(limit: int, rounds: int) -> int:
    _load_env()
    rows = await fetch_pg_mindmaps(limit=max(limit, 16))
    pairs = hydrate_maps(rows)
    if len(pairs) < 10:
        print(f"Need 10 hydratable mindmaps, got {len(pairs)} from {len(rows)} rows")
        return 2
    pairs = pairs[:10]
    _print_maps(pairs)
    use_live = live_llm_enabled()
    if use_live:
        try:
            init_redis_sync()
        except REDIS_ERRORS as exc:
            print(f"Redis init skipped: {exc}")
        llm_service.initialize()
        print("LLM: live qwen (LIVE_LLM=1)")
    else:
        print("LLM: off — LLM actions will fail unless fast-path covers them")

    cases: List[Dict[str, Any]] = []
    for _row, mmap in pairs:
        for action in NODE_ACTIONS:
            for round_n in range(1, rounds + 1):
                if action not in STRUCTURAL_ACTIONS and not use_live:
                    cases.append(
                        {
                            "slug": mmap.slug,
                            "topic": mmap.topic,
                            "branch": mmap.branch_label,
                            "branch_id": mmap.branch_id,
                            "action": action,
                            "round": round_n,
                            "utterance": utterance_for(mmap, action),
                            "ok": False,
                            "errors": ["LIVE_LLM required"],
                            "outcome": "skipped",
                            "reason": "no_llm",
                            "loop_action": "",
                            "tool": "",
                            "command_action": "",
                            "command_node_id": "",
                            "command_target": "",
                            "llm_ms": 0.0,
                            "total_ms": 0.0,
                            "llm_calls": 0,
                        }
                    )
                    continue
                result = await run_one(mmap, action, round_n, use_live_llm=use_live)
                cases.append(result)
                flag = "PASS" if result["ok"] else "FAIL"
                print(f"[{flag}] {mmap.slug}/{action} r{round_n} reason={result['reason']} {result['total_ms']:.0f}ms")

    passed = sum(1 for row in cases if row["ok"])
    report = {
        "maps": [
            {
                "id": row["id"],
                "title": row["title"],
                "slug": mmap.slug,
                "topic": mmap.topic,
                "branch": mmap.branch_label,
                "branch_id": mmap.branch_id,
            }
            for row, mmap in pairs
        ],
        "live_llm": use_live,
        "rounds": rounds,
        "passed": passed,
        "failed": len(cases) - passed,
        "cases": cases,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_results(cases)
    print(f"\n{passed}/{len(cases)} passed  wrote {OUT_JSON}")
    return 0 if passed == len(cases) else 1


def main() -> int:
    """CLI entry: load env maps and run the audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    return asyncio.run(_async_main(limit=args.limit, rounds=args.rounds))


if __name__ == "__main__":
    raise SystemExit(main())
