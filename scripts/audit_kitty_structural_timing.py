"""Time structural Kitty edits: utterance-in to session apply.

Clock starts when the finished voice command (ASR text) enters
``run_typed_agent_loop``. Clock ends when ``execute_diagram_update`` has
mutated session ``diagram_data`` and the WS ``diagram_update`` is sent.

Does not include Fun-ASR, CosyVoice, canvas paint, or canvas ack.
Does not write back to Postgres. Auto-complete is out of scope.

  PYTHONPATH=. python scripts/audit_kitty_structural_timing.py
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

from fastapi import WebSocket
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.agent_hub.diagram_spine.origins import DiagramCommandOrigin
from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.kitty.adapters.diagram_command import (
    apply_kitty_legacy_diagram_command as real_apply,
)
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.agent_loop.tools import dispatch_loop_tool as real_dispatch_loop_tool
from services.kitty.routing.outcomes import RouteOutcome
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.kitty_agent_loop_catalog import (
    STRUCTURAL_ACTIONS,
    RealMindmap,
    load_real_mindmap_from_spec,
    utterance_for,
)
from tests.smoke.mindmap_smoke_helpers import mindmap_smoke_helpers_load_dotenv
from tests.typing_helpers import as_type

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "tmp" / "kitty_structural_apply_timing.json"
TIMING_ACTIONS = ("add_node", "update_node", "update_center", "delete_node")


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


def _texts(diagram_data: Dict[str, Any]) -> List[str]:
    found: List[str] = []
    for key in ("nodes", "children"):
        rows = diagram_data.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                found.append(str(row.get("text") or ""))
            elif isinstance(row, str):
                found.append(row)
    center = diagram_data.get("center")
    if isinstance(center, dict):
        found.append(str(center.get("text") or ""))
    topic = diagram_data.get("topic")
    if isinstance(topic, str):
        found.append(topic)
    return found


def _ids(diagram_data: Dict[str, Any]) -> List[str]:
    found: List[str] = []
    for key in ("nodes", "children"):
        rows = diagram_data.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("id"):
                found.append(str(row.get("id")))
    return found


def _ws_actions(sent: List[Dict[str, Any]]) -> List[str]:
    return [
        str(msg.get("action") or "") for msg in sent if isinstance(msg, dict) and msg.get("type") == "diagram_update"
    ]


def _check_applied(
    action: str,
    mmap: RealMindmap,
    after: Dict[str, Any],
    sent: List[Dict[str, Any]],
) -> List[str]:
    errors: List[str] = []
    texts = _texts(after)
    ids = _ids(after)
    ws_acts = _ws_actions(sent)
    if action == "add_node":
        if not any("扩展阅读" in text for text in texts):
            errors.append("add_missing_扩展阅读")
        if "add_nodes" not in ws_acts:
            errors.append(f"ws={ws_acts}")
    elif action == "update_node":
        if not any("要点提纲" in text for text in texts):
            errors.append("rename_missing_要点提纲")
        if mmap.branch_label in texts and not any("要点提纲" in text for text in texts):
            errors.append("old_label_still_only")
        if "update_nodes" not in ws_acts:
            errors.append(f"ws={ws_acts}")
    elif action == "update_center":
        if not any("导学" in text for text in texts):
            errors.append("center_missing_导学")
        if "update_center" not in ws_acts and "update_nodes" not in ws_acts:
            errors.append(f"ws={ws_acts}")
    elif action == "delete_node":
        if mmap.branch_id in ids:
            errors.append("deleted_id_still_present")
        if mmap.branch_label in texts:
            errors.append("deleted_label_still_present")
        if "remove_nodes" not in ws_acts:
            errors.append(f"ws={ws_acts}")
    return errors


def check_structural_applied(
    action: str,
    mmap: RealMindmap,
    after: Dict[str, Any],
    sent: List[Dict[str, Any]],
) -> List[str]:
    """Public wrapper for in-session structural apply checks."""
    return _check_applied(action, mmap, after, sent)


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


async def run_one(mmap: RealMindmap, action: str, round_n: int) -> Dict[str, Any]:
    """One structural utterance with a real in-memory apply."""
    utterance = utterance_for(mmap, action)
    ws = FakeWs()
    ctx = copy.deepcopy(mmap.context)
    vid = create_voice_session(
        user_id="pg-timing",
        diagram_session_id=f"scope-{mmap.slug}-{action}-r{round_n}",
        diagram_type="mindmap",
    )
    voice_sessions[vid]["context"] = ctx
    voice_sessions[vid]["active_panel"] = "one_sentence"

    apply_ms = 0.0
    apply_n = 0
    command: Dict[str, Any] = {}
    apply_status = ""
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
        nonlocal apply_ms, apply_n, command, apply_status
        del verify_required
        apply_n += 1
        command = dict(legacy_command)
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
        apply_status = str(result.tool_result.status)
        return result

    started = time.perf_counter()
    try:
        with (
            patch(
                "services.kitty.agent_loop.loop.llm_service.chat_raw",
                new=AsyncMock(side_effect=AssertionError("LLM disabled")),
            ),
            patch("services.kitty.agent_loop.loop.dispatch_loop_tool", new=_dispatch),
            patch(
                "services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command",
                new=_timed_apply,
            ),
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
        after = live_ctx.get("diagram_data") if isinstance(live_ctx, dict) else {}
        if not isinstance(after, dict):
            after = {}
        if result.outcome != RouteOutcome.EXECUTED:
            errors.append(f"outcome={result.outcome}")
        if result.reason not in {"fast_structural", "await_canvas"}:
            errors.append(f"reason={result.reason}")
        if result.action != action:
            errors.append(f"loop_action={result.action}")
        if apply_n < 1:
            errors.append("apply_not_called")
        if apply_status and apply_status != "applied":
            errors.append(f"apply_status={apply_status}")
        if command.get("action") != action:
            errors.append(f"command={command.get('action')}")
        errors.extend(_check_applied(action, mmap, after, ws.sent))
        return {
            "slug": mmap.slug,
            "topic": mmap.topic,
            "branch": mmap.branch_label,
            "action": action,
            "round": round_n,
            "utterance": utterance,
            "ok": not errors,
            "errors": errors,
            "reason": str(result.reason or ""),
            "apply_status": apply_status,
            "ws_actions": _ws_actions(ws.sent),
            "route_ms": round(route_ms, 2),
            "apply_ms": round(apply_ms, 2),
            "total_ms": round(total_ms, 2),
        }
    except AssertionError as exc:
        return {
            "slug": mmap.slug,
            "topic": mmap.topic,
            "branch": mmap.branch_label,
            "action": action,
            "round": round_n,
            "utterance": utterance,
            "ok": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "reason": "",
            "apply_status": apply_status,
            "ws_actions": _ws_actions(ws.sent),
            "route_ms": 0.0,
            "apply_ms": round(apply_ms, 2),
            "total_ms": round((time.perf_counter() - started) * 1000.0, 2),
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
    print("\nStructural apply timing (utterance-in → session mutate + WS send)")
    print(f"{'case':<46} {'r':>1} {'ok':<4} {'route':>8} {'apply':>8} {'total':>8}")
    for row in cases:
        case = f"{row['slug']}/{row['action']}"
        flag = "PASS" if row["ok"] else "FAIL"
        print(
            f"{case:<46} {row['round']:>1} {flag:<4} "
            f"{row['route_ms']:8.2f} {row['apply_ms']:8.2f} {row['total_ms']:8.2f}"
        )
        if row["errors"]:
            print(f"    {row['errors']}")


def _by_action(cases: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for action in TIMING_ACTIONS:
        rows = [row for row in cases if row["action"] == action]
        totals = [float(row["total_ms"]) for row in rows]
        applies = [float(row["apply_ms"]) for row in rows]
        routes = [float(row["route_ms"]) for row in rows]
        grouped[action] = {
            "n": len(rows),
            "ok": sum(1 for row in rows if row["ok"]),
            "total": {key: round(val, 2) for key, val in _ms_stats(totals).items()},
            "apply": {key: round(val, 2) for key, val in _ms_stats(applies).items()},
            "route": {key: round(val, 2) for key, val in _ms_stats(routes).items()},
        }
    return grouped


async def _async_main(limit: int, rounds: int) -> int:
    _load_env()
    rows = await fetch_pg_mindmaps(limit=max(limit, 16))
    pairs = hydrate_maps(rows)
    if len(pairs) < 10:
        print(f"Need 10 hydratable mindmaps, got {len(pairs)} from {len(rows)} rows")
        return 2
    pairs = pairs[:10]
    _print_maps(pairs)

    cases: List[Dict[str, Any]] = []
    for _row, mmap in pairs:
        for action in TIMING_ACTIONS:
            if action not in STRUCTURAL_ACTIONS:
                continue
            for round_n in range(1, rounds + 1):
                result = await run_one(mmap, action, round_n)
                cases.append(result)
                flag = "PASS" if result["ok"] else "FAIL"
                print(
                    f"[{flag}] {mmap.slug}/{action} r{round_n} "
                    f"route={result['route_ms']:.2f}ms apply={result['apply_ms']:.2f}ms "
                    f"total={result['total_ms']:.2f}ms"
                )

    passed = sum(1 for row in cases if row["ok"])
    by_action = _by_action(cases)
    all_total = _ms_stats([float(row["total_ms"]) for row in cases])
    all_apply = _ms_stats([float(row["apply_ms"]) for row in cases])
    report = {
        "clock": {
            "start": "utterance handed to run_typed_agent_loop (ASR already done)",
            "end": "execute_diagram_update mutated session diagram_data and sent diagram_update",
            "excluded": [
                "Fun-ASR / PTT release",
                "CosyVoice TTS",
                "canvas paint",
                "canvas mutation ack",
                "hub persist",
                "auto-complete LLM",
            ],
        },
        "note": (
            "No Kitty move_node tool. Structural set is add_node, update_node, "
            "update_center, delete_node. verify_required=False so apply is the "
            "legacy voice mutate path, not the 8s canvas-ack wait."
        ),
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
    _print_results(cases)
    print("\nBy action (total ms = route + apply)")
    print(f"{'action':<16} {'n':>3} {'ok':>3} {'avg':>8} {'p50':>8} {'p95':>8} {'max':>8}")
    for action, stats in by_action.items():
        tot = stats["total"]
        print(
            f"{action:<16} {stats['n']:3d} {stats['ok']:3d} "
            f"{tot['avg']:8.2f} {tot['p50']:8.2f} {tot['p95']:8.2f} {tot['max']:8.2f}"
        )
    print(
        f"\n{passed}/{len(cases)} applied  "
        f"p50={all_total['p50']:.2f}ms  p95={all_total['p95']:.2f}ms  "
        f"max={all_total['max']:.2f}ms  wrote {OUT_JSON}"
    )
    return 0 if passed == len(cases) else 1


def main() -> int:
    """CLI entry: load PG maps and time structural apply."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    return asyncio.run(_async_main(limit=args.limit, rounds=args.rounds))


if __name__ == "__main__":
    raise SystemExit(main())
