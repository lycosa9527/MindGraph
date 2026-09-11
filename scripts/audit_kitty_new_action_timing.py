"""Time new Kitty node actions: utterance-in to session apply.

Clock starts when the finished voice command enters ``run_typed_agent_loop``.
Clock ends when the session spec / preference flag is written and the WS
action or ``diagram_update`` is sent.

Does not include Fun-ASR, CosyVoice, canvas paint, canvas ack, or Hub persist.
Does not write back to Postgres.

  PYTHONPATH=. python scripts/audit_kitty_new_action_timing.py
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import importlib.util
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

from fastapi import WebSocket

from services.agent_hub.diagram_spine.origins import DiagramCommandOrigin
from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.kitty.adapters.diagram_command import (
    apply_kitty_legacy_diagram_command as real_apply,
)
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.agent_loop.tools import dispatch_loop_tool as real_dispatch_loop_tool
from services.kitty.context.messaging import send_kitty_ws_action as real_send_ws
from services.kitty.routing.command_router import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.kitty_agent_loop_catalog import RealMindmap
from tests.smoke.mindmap_smoke_helpers import mindmap_smoke_helpers_load_dotenv
from tests.typing_helpers import as_type

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "tmp" / "kitty_new_action_timing.json"
_NEW_AUDIT = ROOT / "scripts" / "audit_kitty_new_node_actions.py"
_PG_AUDIT = ROOT / "scripts" / "audit_kitty_pg_node_actions.py"


class _WsState:
    """FastAPI-shaped client_state so safe_websocket_send treats us as open."""

    name = "CONNECTED"


class FakeWs:
    """In-process WS: record outbound JSON, never block."""

    def __init__(self) -> None:
        self.sent: List[Dict[str, Any]] = []
        self.client_state = _WsState()

    async def send_json(self, message: Any) -> None:
        """Record one outbound JSON frame."""
        if isinstance(message, dict):
            self.sent.append(message)


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
        "avg": sum(ordered) / len(ordered),
        "p50": ordered[len(ordered) // 2],
        "p95": ordered[p95_i],
        "max": ordered[-1],
    }


def _texts(diagram_data: Dict[str, Any]) -> List[str]:
    found: List[str] = []
    nodes = diagram_data.get("nodes")
    if isinstance(nodes, list):
        for row in nodes:
            if isinstance(row, dict):
                found.append(str(row.get("text") or ""))
    return found


def _ids(diagram_data: Dict[str, Any]) -> List[str]:
    found: List[str] = []
    nodes = diagram_data.get("nodes")
    if isinstance(nodes, list):
        for row in nodes:
            if isinstance(row, dict) and row.get("id"):
                found.append(str(row.get("id")))
    return found


def _check_case(
    action: str,
    targets: Dict[str, Any],
    context: Dict[str, Any],
    sent: List[Dict[str, Any]],
) -> List[str]:
    errors: List[str] = []
    diagram = context.get("diagram_data")
    diagram_dict = diagram if isinstance(diagram, dict) else {}
    ws_types = [str(msg.get("type") or "") for msg in sent]
    ws_actions = [str(msg.get("action") or "") for msg in sent]
    if action == "set_content_level":
        if context.get("ai_content_level") != "primary":
            errors.append("session_level")
        if "set_content_level" not in ws_actions:
            errors.append(f"ws={ws_actions}")
    elif action == "set_content_level_expert":
        if context.get("ai_content_level") != "expert":
            errors.append("session_level")
        if "set_content_level" not in ws_actions:
            errors.append(f"ws={ws_actions}")
    elif action == "set_branch_numbering_decimal":
        if diagram_dict.get("_mindmap_branch_numbering_prefix") != "decimal":
            errors.append("session_prefix")
        if "set_branch_numbering" not in ws_actions:
            errors.append(f"ws={ws_actions}")
    elif action == "set_branch_numbering_chinese":
        if diagram_dict.get("_mindmap_branch_numbering_prefix") != "chinese":
            errors.append("session_prefix")
        if "set_branch_numbering" not in ws_actions:
            errors.append(f"ws={ws_actions}")
    elif action == "set_branch_numbering_on":
        if diagram_dict.get("_mindmap_branch_numbering") is not True:
            errors.append("session_flag")
        if "set_branch_numbering" not in ws_actions:
            errors.append(f"ws={ws_actions}")
    elif action == "set_branch_numbering_off":
        if diagram_dict.get("_mindmap_branch_numbering") is not False:
            errors.append("session_flag")
        if "set_branch_numbering" not in ws_actions:
            errors.append(f"ws={ws_actions}")
    elif action in {"update_node_by_outline", "update_node_by_ordinal"}:
        if not any("要点提纲" in text for text in _texts(diagram_dict)):
            errors.append("rename_missing_要点提纲")
        if "diagram_update" not in ws_types:
            errors.append(f"ws_types={ws_types}")
    elif action == "delete_node_by_ordinal":
        second = targets.get("second")
        if isinstance(second, dict) and second.get("node_id") in _ids(diagram_dict):
            errors.append("deleted_id_still_present")
        if "diagram_update" not in ws_types:
            errors.append(f"ws_types={ws_types}")
    return errors


async def run_one(
    mmap: RealMindmap,
    action: str,
    template: str,
    *,
    numbering_on: bool,
    targets: Dict[str, Any],
    utterance_fn: Any,
    round_n: int,
) -> Dict[str, Any]:
    """One new-action utterance with a real in-memory apply."""
    utterance = utterance_fn(action, template, targets)
    if not utterance:
        return {
            "slug": mmap.slug,
            "action": action,
            "round": round_n,
            "utterance": "",
            "ok": False,
            "errors": ["empty_utterance"],
            "reason": "",
            "route_ms": 0.0,
            "apply_ms": 0.0,
            "total_ms": 0.0,
        }
    ws = FakeWs()
    ctx = copy.deepcopy(mmap.context)
    diagram = ctx.get("diagram_data")
    if numbering_on and isinstance(diagram, dict):
        diagram["_mindmap_branch_numbering"] = True
    vid = create_voice_session(
        user_id="new-timing",
        diagram_session_id=f"scope-{mmap.slug}-{action}-r{round_n}",
        diagram_type="mindmap",
    )
    voice_sessions[vid]["context"] = ctx
    voice_sessions[vid]["active_panel"] = "one_sentence"
    apply_ms = 0.0
    apply_n = 0
    errors: List[str] = []

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
        del verify_required
        return await real_dispatch_loop_tool(
            websocket,
            voice_session_id,
            name=name,
            arguments_json=arguments_json,
            session_context=session_context,
            diagram_type=diagram_type,
            command_text=command_text,
            verify_required=False,
        )

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
        nonlocal apply_ms, apply_n
        del verify_required
        apply_n += 1
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
        apply_ms += (time.perf_counter() - started) * 1000.0
        return result

    async def _timed_ws(*args: Any, **kwargs: Any) -> Any:
        nonlocal apply_ms, apply_n
        apply_n += 1
        started = time.perf_counter()
        result = await real_send_ws(*args, **kwargs)
        apply_ms += (time.perf_counter() - started) * 1000.0
        return result

    started = time.perf_counter()
    try:
        with (
            patch(
                "services.kitty.agent_loop.loop.llm_service.chat_raw",
                new=AsyncMock(side_effect=AssertionError("LLM disabled")),
            ),
            patch("services.kitty.agent_loop.loop.dispatch_loop_tool", new=_dispatch),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", new=_timed_apply),
            patch("services.kitty.agent_loop.preference_tools.send_kitty_ws_action", new=_timed_ws),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.preference_tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch(
                "services.kitty.agent_loop.preference_tools.fanout_voice_command_from_session",
                new=AsyncMock(),
            ),
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
        route_ms = max(0.0, total_ms - apply_ms)
        live = voice_sessions.get(vid) or {}
        live_ctx = live.get("context") if isinstance(live, dict) else {}
        session_ctx = live_ctx if isinstance(live_ctx, dict) else ctx
        if result.outcome != RouteOutcome.EXECUTED:
            errors.append(f"outcome={result.outcome}")
        expect_reason = "fast_preference" if action.startswith("set_") else "fast_structural"
        if result.reason != expect_reason:
            errors.append(f"reason={result.reason}")
        if apply_n < 1:
            errors.append("apply_not_called")
        errors.extend(_check_case(action, targets, session_ctx, ws.sent))
        return {
            "slug": mmap.slug,
            "topic": mmap.topic,
            "action": action,
            "round": round_n,
            "utterance": utterance,
            "ok": not errors,
            "errors": errors,
            "reason": str(result.reason or ""),
            "route_ms": round(route_ms, 2),
            "apply_ms": round(apply_ms, 2),
            "total_ms": round(total_ms, 2),
        }
    except AssertionError as exc:
        return {
            "slug": mmap.slug,
            "topic": mmap.topic,
            "action": action,
            "round": round_n,
            "utterance": utterance,
            "ok": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "reason": "",
            "route_ms": 0.0,
            "apply_ms": round(apply_ms, 2),
            "total_ms": round((time.perf_counter() - started) * 1000.0, 2),
        }
    finally:
        voice_sessions.pop(vid, None)


def _by_action(cases: List[Dict[str, Any]], action_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for action in action_ids:
        rows = [row for row in cases if row["action"] == action]
        grouped[action] = {
            "n": len(rows),
            "ok": sum(1 for row in rows if row["ok"]),
            "total": {key: round(val, 2) for key, val in _ms_stats([float(row["total_ms"]) for row in rows]).items()},
            "apply": {key: round(val, 2) for key, val in _ms_stats([float(row["apply_ms"]) for row in rows]).items()},
            "route": {key: round(val, 2) for key, val in _ms_stats([float(row["route_ms"]) for row in rows]).items()},
        }
    return grouped


async def _async_main(limit: int, rounds: int) -> int:
    mindmap_smoke_helpers_load_dotenv(ROOT / ".env")
    pg_audit = _load_module(_PG_AUDIT, "audit_kitty_pg_node_actions")
    new_audit = _load_module(_NEW_AUDIT, "audit_kitty_new_node_actions")
    rows = await pg_audit.fetch_pg_mindmaps(limit=max(limit, 16))
    pairs = pg_audit.hydrate_maps(rows)
    if len(pairs) < 10:
        print(f"Need 10 hydratable mindmaps, got {len(pairs)} from {len(rows)} rows")
        return 2
    pairs = pairs[:10]
    targets_by_slug = {
        mmap.slug: new_audit.outline_index(mmap.context.get("diagram_data") or {}) for _row, mmap in pairs
    }
    action_ids = [item[0] for item in new_audit.CASE_SPECS]
    cases: List[Dict[str, Any]] = []
    for _row, mmap in pairs:
        targets = targets_by_slug[mmap.slug]
        for action, template, numbering_on in new_audit.CASE_SPECS:
            for round_n in range(1, rounds + 1):
                result = await run_one(
                    mmap,
                    action,
                    template,
                    numbering_on=numbering_on,
                    targets=targets,
                    utterance_fn=new_audit.utterance_for_new_action,
                    round_n=round_n,
                )
                cases.append(result)
                flag = "PASS" if result["ok"] else "FAIL"
                print(
                    f"[{flag}] {mmap.slug}/{action} r{round_n} "
                    f"route={result['route_ms']:.2f} apply={result['apply_ms']:.2f} "
                    f"total={result['total_ms']:.2f}"
                )
                if result["errors"]:
                    print(f"    {result['errors']}")

    passed = sum(1 for row in cases if row["ok"])
    by_action = _by_action(cases, action_ids)
    all_total = _ms_stats([float(row["total_ms"]) for row in cases])
    all_apply = _ms_stats([float(row["apply_ms"]) for row in cases])
    report = {
        "clock": {
            "start": "utterance handed to run_typed_agent_loop (ASR already done)",
            "end": "session flag/spec mutated and WS action or diagram_update sent",
            "excluded": [
                "Fun-ASR / PTT release",
                "CosyVoice TTS",
                "canvas paint",
                "canvas mutation ack",
                "hub persist",
            ],
        },
        "maps": [{"title": row["title"], "slug": mmap.slug, "topic": mmap.topic} for row, mmap in pairs],
        "rounds": rounds,
        "passed": passed,
        "failed": len(cases) - passed,
        "overall_total_ms": {key: round(val, 2) for key, val in all_total.items()},
        "overall_apply_ms": {key: round(val, 2) for key, val in all_apply.items()},
        "by_action": by_action,
        "cases": cases,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nBy action (total ms = route + apply)")
    print(f"{'action':<32} {'n':>3} {'ok':>3} {'p50':>8} {'p95':>8} {'max':>8} {'p50 apply':>10}")
    for action, stats in by_action.items():
        tot = stats["total"]
        print(
            f"{action:<32} {stats['n']:3d} {stats['ok']:3d} "
            f"{tot['p50']:8.2f} {tot['p95']:8.2f} {tot['max']:8.2f} "
            f"{stats['apply']['p50']:10.2f}"
        )
    print(
        f"\n{passed}/{len(cases)} applied  "
        f"p50={all_total['p50']:.2f}ms  p95={all_total['p95']:.2f}ms  "
        f"max={all_total['max']:.2f}ms  wrote {OUT_JSON}"
    )
    return 0 if passed == len(cases) else 1


def main() -> int:
    """CLI entry: load PG maps and time new-action apply."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    return asyncio.run(_async_main(limit=args.limit, rounds=args.rounds))


if __name__ == "__main__":
    raise SystemExit(main())
