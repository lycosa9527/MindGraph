"""Live audit: five stacked teacher sentences on ten Postgres mindmaps.

In-session apply only. No library writeback. Auto-complete generation is stubbed;
planning uses live qwen3.8-flash.

  LIVE_LLM=1 PYTHONPATH=. python -u scripts/audit_kitty_compound_live.py
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import importlib.util
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from fastapi import WebSocket

from services.agent_hub.diagram_spine.origins import DiagramCommandOrigin
from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.kitty.adapters.diagram_command import (
    apply_kitty_legacy_diagram_command as real_apply,
)
from services.kitty.agent_loop.loop import AGENT_LOOP_MODEL, run_typed_agent_loop
from services.kitty.routing.outcomes import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.llm import llm_service
from services.redis.redis_client import init_redis_sync
from services.utils.error_types import LLM_PIPELINE_ERRORS, REDIS_ERRORS
from tests.kitty_agent_loop_catalog import RealMindmap
from tests.smoke.mindmap_smoke_helpers import live_llm_enabled, mindmap_smoke_helpers_load_dotenv
from tests.typing_helpers import as_type

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "tmp" / "kitty_compound_upgrade_audit.json"
_PG_AUDIT = ROOT / "scripts" / "audit_kitty_pg_node_actions.py"
_TIMING = ROOT / "scripts" / "audit_kitty_structural_timing.py"

ADD_ONE = "扩展阅读"
ADD_A = "要点提纲"
ADD_B = "课堂练习"
RENAME_TO = "课堂导入"
ADD_GEO = "地理"


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ms_stats(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"n": 0.0, "avg": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    ordered = sorted(values)
    p95_i = min(len(ordered) - 1, max(0, int(round(0.95 * (len(ordered) - 1)))))
    return {
        "n": float(len(ordered)),
        "avg": round(sum(ordered) / len(ordered), 1),
        "p50": round(ordered[len(ordered) // 2], 1),
        "p95": round(ordered[p95_i], 1),
        "max": round(ordered[-1], 1),
    }


def _texts(diagram_data: Dict[str, Any]) -> List[str]:
    found: List[str] = []
    nodes = diagram_data.get("nodes")
    if isinstance(nodes, list):
        for row in nodes:
            if isinstance(row, dict):
                found.append(str(row.get("text") or ""))
    center = diagram_data.get("center")
    if isinstance(center, dict):
        found.append(str(center.get("text") or ""))
    return found


def _diagram_from_session(vid: str) -> Dict[str, Any]:
    live = voice_sessions.get(vid) or {}
    live_ctx = live.get("context") if isinstance(live, dict) else {}
    after = live_ctx.get("diagram_data") if isinstance(live_ctx, dict) else {}
    return after if isinstance(after, dict) else {}


def compound_cases(mmap: RealMindmap) -> Tuple[Tuple[str, str], ...]:
    """Five stacked teacher sentences. Labels stay teacher-generic."""
    topic = mmap.topic
    branch = mmap.branch_label
    return (
        ("center_then_add", f"主题改成{topic}导学，再添加一个{ADD_ONE}的分支"),
        ("two_named_adds", f"再加两个分支：{ADD_A}、{ADD_B}"),
        ("center_then_fill", f"把主题改成{topic}，并自动补完这幅思维导图"),
        ("add_then_fill", f"添加一个{ADD_ONE}的分支并补全"),
        ("delete_then_add", f"删除{branch}这个分支，再加一个{ADD_GEO}的分支"),
    )


def _tool_names(recorded: List[Dict[str, Any]]) -> List[str]:
    names: List[str] = []
    for row in recorded:
        calls = row.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            fn = call.get("function")
            if isinstance(fn, dict) and isinstance(fn.get("name"), str):
                names.append(fn["name"])
    return names


def _applied_actions(applies: List[Dict[str, str]]) -> List[str]:
    return [row.get("action") or "" for row in applies if row.get("status") == "applied"]


def _applied_targets(applies: List[Dict[str, str]]) -> str:
    return " ".join(row.get("target") or "" for row in applies)


def _score(
    action: str,
    mmap: RealMindmap,
    after: Dict[str, Any],
    applies: List[Dict[str, str]],
    result: Any,
    tools: List[str],
    ui_actions: List[str],
) -> List[str]:
    errors: List[str] = []
    texts = "".join(_texts(after))
    applied = _applied_actions(applies)
    targets = _applied_targets(applies)
    if result.outcome != RouteOutcome.EXECUTED:
        errors.append(f"outcome={result.outcome}")
    if result.reason == "fast_structural":
        errors.append("fast_structural")
    if action == "center_then_add":
        if f"{mmap.topic}导学" not in texts and f"{mmap.topic}导学" not in targets:
            errors.append("center_missing_导学")
        if ADD_ONE not in texts and ADD_ONE not in targets:
            errors.append(f"missing_{ADD_ONE}")
        if applied.count("add_node") < 1:
            errors.append(f"adds={applied.count('add_node')}")
    elif action == "two_named_adds":
        if ADD_A not in texts and ADD_A not in targets:
            errors.append(f"missing_{ADD_A}")
        if ADD_B not in texts and ADD_B not in targets:
            errors.append(f"missing_{ADD_B}")
        if applied.count("add_node") < 2:
            errors.append(f"adds={applied.count('add_node')}")
    elif action == "center_then_fill":
        if mmap.topic not in texts and mmap.topic not in targets:
            errors.append("center_missing")
        if "node_action.auto_complete" not in tools and "auto_complete" not in ui_actions:
            errors.append("no_auto_complete")
    elif action == "add_then_fill":
        if ADD_ONE not in texts and ADD_ONE not in targets:
            errors.append(f"missing_{ADD_ONE}")
        if "node_action.auto_complete_branch" not in tools and "auto_complete_branch" not in ui_actions:
            errors.append("no_branch_fill")
    elif action == "delete_then_add":
        if applied.count("delete_node") < 1:
            errors.append("no_delete")
        if ADD_GEO not in texts and ADD_GEO not in targets:
            errors.append(f"missing_{ADD_GEO}")
    return errors


async def run_one(
    mmap: RealMindmap,
    action: str,
    utterance: str,
    *,
    fake_ws_cls: Any,
) -> Dict[str, Any]:
    """One stacked utterance on a deep-copied session."""
    ws = fake_ws_cls()
    ctx = copy.deepcopy(mmap.context)
    vid = create_voice_session(
        user_id="compound-upgrade",
        diagram_session_id=f"scope-{mmap.slug}-{action}",
        diagram_type="mindmap",
    )
    voice_sessions[vid]["context"] = ctx
    voice_sessions[vid]["active_panel"] = "one_sentence"
    applies: List[Dict[str, str]] = []
    ui_actions: List[str] = []
    recorded: List[Dict[str, Any]] = []
    apply_ms = 0.0
    llm_ms = 0.0
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

    async def _timed_apply(
        websocket: Any,
        voice_session_id: str,
        legacy_command: Dict[str, Any],
        session_context: Dict[str, Any],
        *,
        scope: str,
        diagram_type: str,
        user_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        verify_required: bool = True,
        origin: DiagramCommandOrigin = DiagramCommandOrigin.KITTY_MOBILE,
        user_text: str = "",
        grounding_source: str = "",
    ) -> DiagramCommandResult:
        del verify_required
        started = time.perf_counter()
        result = await real_apply(
            websocket,
            voice_session_id,
            legacy_command,
            session_context,
            scope=scope,
            diagram_type=diagram_type,
            user_id=user_id,
            idempotency_key=idempotency_key,
            verify_required=False,
            origin=origin,
            user_text=user_text,
            grounding_source=grounding_source,
        )
        nonlocal apply_ms
        apply_ms += (time.perf_counter() - started) * 1000.0
        stamped_id = ""
        if str(legacy_command.get("action") or "") == "add_node" and result.tool_result.status == "applied":
            stamped_id = f"uid-ph-{len(applies)}"
            label = str(legacy_command.get("target") or "")
            result.tool_result.applied_ops = [
                {"op": "add_node", "node_id": stamped_id, "text": label},
            ]
            live = voice_sessions.get(voice_session_id)
            live_ctx = live.get("context") if isinstance(live, dict) else None
            diagram = live_ctx.get("diagram_data") if isinstance(live_ctx, dict) else None
            if isinstance(diagram, dict) and label:
                row = {"id": stamped_id, "text": label}
                children = diagram.get("children")
                nodes = diagram.get("nodes")
                if isinstance(children, list):
                    children.append(row)
                if isinstance(nodes, list):
                    nodes.append(row)
        applies.append(
            {
                "action": str(legacy_command.get("action") or ""),
                "target": str(legacy_command.get("target") or legacy_command.get("new_text") or "")[:40],
                "status": str(result.tool_result.status),
                "node_id": stamped_id,
            }
        )
        return result

    async def _capture_ac(*_args: Any, **_kwargs: Any) -> bool:
        ui_actions.append("auto_complete_branch")
        return True

    async def _capture_ws(_ws: Any, _vid: str, message: Any, **_kwargs: Any) -> bool:
        if isinstance(message, dict) and message.get("action") == "auto_complete":
            ui_actions.append("auto_complete")
        return True

    started = time.perf_counter()
    errors: List[str] = []
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", new=_chat),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", new=_timed_apply),
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                new=AsyncMock(return_value=False),
            ),
            patch("services.kitty.agent_loop.tools.emit_auto_complete_branch", new=_capture_ac),
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", new=_capture_ws),
            patch("services.kitty.agent_loop.compound.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.interrupt_kitty_tts", new=AsyncMock()),
            patch("services.kitty.agent_loop.loop.persist_armed_intent_slot", new=AsyncMock()),
            patch("services.kitty.agent_loop.loop.load_kitty_live_context", new=AsyncMock(return_value=None)),
            patch(
                "services.kitty.agent_loop.loop.throttled_refresh_voice_context_from_library",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.agent_loop.loop.live_spec_newer_than_library",
                new=AsyncMock(return_value=True),
            ),
            patch("services.kitty.agent_loop.loop.fanout_voice_phase_from_session", new=AsyncMock()),
            patch("services.kitty.agent_loop.tools.fanout_voice_command_from_session", new=AsyncMock()),
            patch("services.kitty.diagram.diagram_execute.try_sync_voice_diagram_to_hub", new=AsyncMock()),
            patch("services.kitty.context.messaging.publish_kitty_diagram_update", new=AsyncMock(return_value=True)),
        ):
            result = await run_typed_agent_loop(as_type(ws, WebSocket), vid, utterance, ctx)
        total_ms = (time.perf_counter() - started) * 1000.0
        after = _diagram_from_session(vid)
        tools = _tool_names(recorded)
        errors.extend(_score(action, mmap, after, applies, result, tools, ui_actions))
        path = "llm" if recorded else str(result.reason or "unknown")
        return {
            "slug": mmap.slug,
            "topic": mmap.topic,
            "branch": mmap.branch_label,
            "action": action,
            "utterance": utterance,
            "ok": not errors,
            "errors": errors,
            "outcome": str(result.outcome),
            "reason": str(result.reason or ""),
            "loop_action": str(result.action or ""),
            "path": path,
            "model": AGENT_LOOP_MODEL if recorded else "",
            "tools": tools,
            "ui_actions": ui_actions,
            "applies": applies,
            "apply_n": len(applies),
            "applied_n": sum(1 for row in applies if row.get("status") == "applied"),
            "llm_ms": round(llm_ms, 1),
            "apply_ms": round(apply_ms, 1),
            "total_ms": round(total_ms, 1),
            "llm_calls": len(recorded),
        }
    except (*LLM_PIPELINE_ERRORS, AssertionError) as exc:
        return {
            "slug": mmap.slug,
            "topic": mmap.topic,
            "branch": mmap.branch_label,
            "action": action,
            "utterance": utterance,
            "ok": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "outcome": "error",
            "reason": "",
            "loop_action": "",
            "path": "error",
            "model": AGENT_LOOP_MODEL,
            "tools": _tool_names(recorded),
            "ui_actions": ui_actions,
            "applies": applies,
            "apply_n": len(applies),
            "applied_n": sum(1 for row in applies if row.get("status") == "applied"),
            "llm_ms": round(llm_ms, 1),
            "apply_ms": round(apply_ms, 1),
            "total_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "llm_calls": len(recorded),
        }
    finally:
        voice_sessions.pop(vid, None)


def _print_maps(pairs: List[tuple[Dict[str, Any], RealMindmap]]) -> None:
    print("\nPostgres mindmaps")
    for _row, mmap in pairs:
        nodes = mmap.context.get("diagram_data", {}).get("nodes")
        n_nodes = len(nodes) if isinstance(nodes, list) else 0
        print(f"{mmap.slug:<32} {mmap.topic[:18]:<20} L1={mmap.branch_label[:16]:<18} n={n_nodes}")


async def _async_main(limit: int) -> int:
    mindmap_smoke_helpers_load_dotenv(ROOT / ".env")
    if not live_llm_enabled():
        print("Need LIVE_LLM=1 and QWEN_API_KEY")
        return 2
    pg_mod = _load_module(_PG_AUDIT, "audit_kitty_pg_node_actions")
    timing_mod = _load_module(_TIMING, "audit_kitty_structural_timing")
    rows = await pg_mod.fetch_pg_mindmaps(limit=max(limit, 16))
    pairs = pg_mod.hydrate_maps(rows)
    if len(pairs) < 10:
        print(f"Need 10 hydratable mindmaps, got {len(pairs)} from {len(rows)} rows")
        return 2
    pairs = pairs[:10]
    _print_maps(pairs)
    try:
        init_redis_sync()
    except REDIS_ERRORS as exc:
        print(f"Redis init skipped: {exc}")
    llm_service.initialize()
    print(f"LLM: live {AGENT_LOOP_MODEL}")

    cases: List[Dict[str, Any]] = []
    wall_started = time.perf_counter()
    for _row, mmap in pairs:
        for action, utterance in compound_cases(mmap):
            result = await run_one(
                mmap,
                action,
                utterance,
                fake_ws_cls=timing_mod.FakeWs,
            )
            cases.append(result)
            flag = "PASS" if result["ok"] else "FAIL"
            tools = ",".join(result.get("tools") or [])
            print(
                f"[{flag}] {mmap.slug}/{action} "
                f"path={result['path']} reason={result['reason']} "
                f"llm={result['llm_calls']}@{result['llm_ms']:.0f}ms "
                f"apply={result['applied_n']}@{result['apply_ms']:.0f}ms "
                f"total={result['total_ms']:.0f}ms "
                f"tools={tools} {result['errors']}"
            )

    wall_ms = (time.perf_counter() - wall_started) * 1000.0
    names = [action for action, _utterance in compound_cases(pairs[0][1])]
    by_action = {name: [row for row in cases if row.get("action") == name] for name in names}
    report = {
        "model": AGENT_LOOP_MODEL,
        "maps": [
            {
                "id": row["id"],
                "title": row["title"],
                "slug": mmap.slug,
                "topic": mmap.topic,
                "branch": mmap.branch_label,
            }
            for row, mmap in pairs
        ],
        "commands": names,
        "wall_ms": round(wall_ms, 1),
        "passed": sum(1 for row in cases if row["ok"]),
        "n": len(cases),
        "timing_all_ms": _ms_stats([float(row.get("total_ms") or 0) for row in cases]),
        "timing_llm_ms": _ms_stats([float(row.get("llm_ms") or 0) for row in cases]),
        "timing_apply_ms": _ms_stats([float(row.get("apply_ms") or 0) for row in cases]),
        "timing_by_action_ms": {
            name: _ms_stats([float(row.get("total_ms") or 0) for row in rows]) for name, rows in by_action.items()
        },
        "llm_by_action_ms": {
            name: _ms_stats([float(row.get("llm_ms") or 0) for row in rows]) for name, rows in by_action.items()
        },
        "llm_calls": sum(int(row.get("llm_calls") or 0) for row in cases),
        "cases": cases,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\n{report['passed']}/{report['n']}  "
        f"model={AGENT_LOOP_MODEL}  llm_calls={report['llm_calls']}  "
        f"p50_total={report['timing_all_ms']['p50']}ms  "
        f"p50_llm={report['timing_llm_ms']['p50']}ms  "
        f"wall {wall_ms / 1000:.1f}s  wrote {OUT_JSON}"
    )
    return 0 if report["passed"] == report["n"] else 1


def main() -> int:
    """CLI entry for the compound-command live timing audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=16)
    args = parser.parse_args()
    return asyncio.run(_async_main(limit=args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
