"""Live audit: five compound edits on ten Postgres mindmaps.

In-session apply only. No library writeback, no canvas verify, no CosyVoice.
Named and vague stacks must not call the LLM.

  PYTHONPATH=. python -u scripts/audit_kitty_compound_live.py
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
from services.kitty.agent_loop.compound import parse_compound_turn
from services.kitty.agent_loop.intent_clarify import PENDING_INTENT_SLOT_KEY
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.routing.outcomes import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.redis.redis_client import init_redis_sync
from services.utils.error_types import REDIS_ERRORS
from tests.kitty_agent_loop_catalog import RealMindmap
from tests.smoke.mindmap_smoke_helpers import mindmap_smoke_helpers_load_dotenv
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
        ("vague_two", f"主题改成{topic}导学，再加两个分支"),
        ("delete_then_add", f"删除{branch}这个分支，再加一个{ADD_GEO}的分支"),
        ("rename_then_add", f"把{branch}改成{RENAME_TO}，再加一个{ADD_B}的分支"),
    )


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
    llm_calls: int,
    acks: List[str],
    slot: Any,
) -> List[str]:
    errors: List[str] = []
    texts = "".join(_texts(after))
    actions = _applied_actions(applies)
    targets = _applied_targets(applies)
    if result.outcome != RouteOutcome.EXECUTED:
        errors.append(f"outcome={result.outcome}")
    if llm_calls:
        errors.append(f"llm_calls={llm_calls}")
    if len(acks) != 1:
        errors.append(f"acks={len(acks)}")
    if action == "vague_two":
        if result.reason != "fast_compound_vague":
            errors.append(f"reason={result.reason}")
        if f"{mmap.topic}导学" not in texts and f"{mmap.topic}导学" not in targets:
            errors.append("center_missing_导学")
        if actions.count("add_node") < 2:
            errors.append(f"adds={actions.count('add_node')}")
        if "新分支" not in targets and "新分支" not in texts:
            errors.append("missing_placeholder")
        if not (isinstance(slot, dict) and len(slot.get("node_ids") or []) == 2):
            errors.append("slot_node_ids")
        if acks and "叫什么" not in acks[0]:
            errors.append("no_ask")
        return errors
    if result.reason != "fast_compound":
        errors.append(f"reason={result.reason}")
    if action == "center_then_add":
        if f"{mmap.topic}导学" not in texts and f"{mmap.topic}导学" not in targets:
            errors.append("center_missing_导学")
        if ADD_ONE not in texts and ADD_ONE not in targets:
            errors.append(f"missing_{ADD_ONE}")
        if actions.count("add_node") < 1:
            errors.append(f"adds={actions.count('add_node')}")
    if action == "two_named_adds":
        if ADD_A not in texts and ADD_A not in targets:
            errors.append(f"missing_{ADD_A}")
        if ADD_B not in texts and ADD_B not in targets:
            errors.append(f"missing_{ADD_B}")
        if actions.count("add_node") < 2:
            errors.append(f"adds={actions.count('add_node')}")
    if action == "delete_then_add":
        if actions.count("delete_node") < 1:
            errors.append("no_delete")
        if ADD_GEO not in texts and ADD_GEO not in targets:
            errors.append(f"missing_{ADD_GEO}")
    if action == "rename_then_add":
        if RENAME_TO not in texts and RENAME_TO not in targets:
            errors.append(f"missing_{RENAME_TO}")
        if ADD_B not in texts and ADD_B not in targets:
            errors.append(f"missing_{ADD_B}")
    return errors


async def run_one(
    mmap: RealMindmap,
    action: str,
    utterance: str,
    *,
    fake_ws_cls: Any,
) -> Dict[str, Any]:
    """One compound utterance on a deep-copied session."""
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
    acks: List[str] = []
    apply_ms = 0.0
    llm_calls = 0

    async def _forbid_llm(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal llm_calls
        llm_calls += 1
        raise AssertionError("compound path must not call chat_raw")

    async def _capture_ack(_ws: Any, _vid: str, message: str, **_kwargs: Any) -> bool:
        acks.append(message)
        return True

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

    started = time.perf_counter()
    parsed = parse_compound_turn(utterance)
    errors: List[str] = []
    slot: Any = None
    try:
        with (
            patch("services.kitty.agent_loop.loop.llm_service.chat_raw", new=_forbid_llm),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", new=_timed_apply),
            patch(
                "services.kitty.agent_loop.tools.maybe_start_background_branch_autocomplete",
                new=AsyncMock(return_value=False),
            ),
            patch("services.kitty.agent_loop.tools.emit_auto_complete_branch", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.compound.emit_user_ack", new=_capture_ack),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.interrupt_kitty_tts", new=AsyncMock()),
            patch("services.kitty.agent_loop.compound.persist_armed_intent_slot", new=AsyncMock()),
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
            patch(
                "services.kitty.agent_loop.loop.fanout_voice_phase_from_session",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.diagram.diagram_execute.try_sync_voice_diagram_to_hub",
                new=AsyncMock(),
            ),
            patch(
                "services.kitty.context.messaging.publish_kitty_diagram_update",
                new=AsyncMock(return_value=True),
            ),
        ):
            result = await run_typed_agent_loop(as_type(ws, WebSocket), vid, utterance, ctx)
        total_ms = (time.perf_counter() - started) * 1000.0
        after = _diagram_from_session(vid)
        live = voice_sessions.get(vid) or {}
        slot = live.get(PENDING_INTENT_SLOT_KEY) if isinstance(live, dict) else None
        errors.extend(_score(action, mmap, after, applies, result, llm_calls, acks, slot))
        if parsed is None:
            errors.append("parse_none")
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
            "ack": acks[0] if acks else "",
            "applies": applies,
            "apply_n": len(applies),
            "applied_n": sum(1 for row in applies if row.get("status") == "applied"),
            "apply_ms": round(apply_ms, 1),
            "total_ms": round(total_ms, 1),
            "llm_calls": llm_calls,
            "parse_kind": parsed.kind if parsed is not None else "",
            "slot": slot if isinstance(slot, dict) else None,
        }
    except AssertionError as exc:
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
            "ack": acks[0] if acks else "",
            "applies": applies,
            "apply_n": len(applies),
            "applied_n": sum(1 for row in applies if row.get("status") == "applied"),
            "apply_ms": round(apply_ms, 1),
            "total_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "llm_calls": llm_calls,
            "parse_kind": parsed.kind if parsed is not None else "",
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
            print(
                f"[{flag}] {mmap.slug}/{action} "
                f"apply={result['applied_n']} {result['total_ms']:.0f}ms "
                f"{result['reason']} {result['errors']}"
            )

    wall_ms = (time.perf_counter() - wall_started) * 1000.0
    by_action = {
        name: [row for row in cases if row.get("action") == name]
        for name in ("center_then_add", "two_named_adds", "vague_two", "delete_then_add", "rename_then_add")
    }
    report = {
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
        "commands": [action for action, _utterance in compound_cases(pairs[0][1])],
        "wall_ms": round(wall_ms, 1),
        "passed": sum(1 for row in cases if row["ok"]),
        "n": len(cases),
        "timing_all_ms": _ms_stats([float(row.get("total_ms") or 0) for row in cases]),
        "timing_apply_ms": _ms_stats([float(row.get("apply_ms") or 0) for row in cases]),
        "timing_by_action_ms": {
            name: _ms_stats([float(row.get("total_ms") or 0) for row in rows]) for name, rows in by_action.items()
        },
        "llm_calls": sum(int(row.get("llm_calls") or 0) for row in cases),
        "cases": cases,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\n{report['passed']}/{report['n']}  "
        f"llm={report['llm_calls']}  "
        f"p50={report['timing_all_ms']['p50']}ms  "
        f"wall {wall_ms / 1000:.1f}s  wrote {OUT_JSON}"
    )
    return 0 if report["passed"] == report["n"] else 1


def main() -> int:
    """CLI entry for the compound-command upgrade audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=16)
    args = parser.parse_args()
    return asyncio.run(_async_main(limit=args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
