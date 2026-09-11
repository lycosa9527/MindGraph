"""Audit new Kitty node actions on ten Postgres mindmaps.

Covers 专业内容, numbering styles, and rename/delete by outline number.
Does not write back to Postgres. Bus / WS apply are captured, not persisted.

  PYTHONPATH=. python scripts/audit_kitty_new_node_actions.py
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
from unittest.mock import AsyncMock, MagicMock, patch

from services.agent_hub.diagram_spine.types import DiagramCommandResult
from services.diagram_edit.types import ToolResult
from services.kitty.agent_loop.loop import run_typed_agent_loop
from services.kitty.agent_loop.tools import dispatch_loop_tool as real_dispatch_loop_tool
from services.kitty.routing.outcomes import RouteOutcome
from services.kitty.routing.mindmap_branch_numbers import build_outline_number_by_id
from services.kitty.session.ops import create_voice_session
from services.kitty.session.runtime_state import voice_sessions
from tests.kitty_agent_loop_catalog import RealMindmap
from tests.smoke.mindmap_smoke_helpers import mindmap_smoke_helpers_load_dotenv
from tests.typing_helpers import mock_await_args

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "tmp" / "kitty_new_node_action_audit.json"
_PG_AUDIT = ROOT / "scripts" / "audit_kitty_pg_node_actions.py"

CASE_SPECS: tuple[tuple[str, str, bool], ...] = (
    ("set_content_level", "专业内容改成小学", False),
    ("set_content_level_expert", "改成专家水平", False),
    ("set_branch_numbering_decimal", "启用数字编号", False),
    ("set_branch_numbering_chinese", "启用中文编号", False),
    ("set_branch_numbering_on", "启用编号", False),
    ("set_branch_numbering_off", "隐藏编号", True),
    ("update_node_by_outline", "", True),
    ("update_node_by_ordinal", "", True),
    ("delete_node_by_ordinal", "", True),
)


def _load_pg_audit() -> Any:
    spec = importlib.util.spec_from_file_location("audit_kitty_pg_node_actions", _PG_AUDIT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load audit_kitty_pg_node_actions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _applied(action: str, node_id: Optional[str]) -> DiagramCommandResult:
    applied_ops = [{"op": action, "node_id": node_id}] if node_id else [{"op": action}]
    return DiagramCommandResult(
        tool_result=ToolResult(
            status="applied",
            mutation_id="new-action-audit",
            revision=2,
            applied_ops=applied_ops,
        ),
        hub_revision=2,
    )


def _node_label(diagram: Dict[str, Any], node_id: str) -> str:
    nodes = diagram.get("nodes")
    if not isinstance(nodes, list):
        return ""
    for node in nodes:
        if isinstance(node, dict) and str(node.get("id") or "") == node_id:
            return str(node.get("text") or "").strip()
    return ""


def outline_index(diagram: Dict[str, Any]) -> Dict[str, Any]:
    """Pick 2.1 (or first dotted) and L1 #2 for number-targeted edits."""
    numbers = build_outline_number_by_id(diagram)
    by_no = {no: nid for nid, no in numbers.items()}
    dotted = sorted(no for no in by_no if "." in no)
    l1 = sorted((no for no in by_no if "." not in no), key=lambda raw: int(raw) if raw.isdigit() else 99)

    def pack(token: Optional[str]) -> Optional[Dict[str, str]]:
        if not token:
            return None
        node_id = by_no.get(token)
        if not node_id:
            return None
        return {"no": token, "node_id": node_id, "label": _node_label(diagram, node_id)}

    preferred_dot = "2.1" if "2.1" in by_no else (dotted[0] if dotted else None)
    preferred_l1 = "2" if "2" in by_no else (l1[1] if len(l1) > 1 else None)
    return {
        "dotted": pack(preferred_dot),
        "second": pack(preferred_l1),
        "l1_count": len(l1),
        "dotted_count": len(dotted),
    }


def utterance_for_new_action(action: str, template: str, targets: Dict[str, Any]) -> str:
    """Spoken phrase for one new-action audit case."""
    return _utterance(action, template, targets)


def _utterance(action: str, template: str, targets: Dict[str, Any]) -> str:
    if action == "update_node_by_outline":
        dotted = targets.get("dotted")
        if isinstance(dotted, dict):
            return f"把{dotted['no']}改成要点提纲"
        return ""
    if action == "update_node_by_ordinal":
        second = targets.get("second")
        if isinstance(second, dict):
            return f"把第{second['no']}个改成要点提纲"
        return ""
    if action == "delete_node_by_ordinal":
        second = targets.get("second")
        if isinstance(second, dict):
            return f"删除第{second['no']}个分支"
        return ""
    return template


def _ws_payload(ws_mock: AsyncMock) -> Dict[str, Any]:
    if not ws_mock.await_count:
        return {}
    args = mock_await_args(ws_mock)
    if len(args) < 3 or not isinstance(args[2], dict):
        return {}
    return args[2]


def _ok_preference(action: str, payload: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    raw_params = payload.get("params")
    params: Dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
    diagram = context.get("diagram_data")
    diagram_dict = diagram if isinstance(diagram, dict) else {}
    if action == "set_content_level":
        if payload.get("action") != "set_content_level" or params.get("level") != "primary":
            errors.append(f"level={params.get('level')}")
        if context.get("ai_content_level") != "primary":
            errors.append("session_level")
    elif action == "set_content_level_expert":
        if payload.get("action") != "set_content_level" or params.get("level") != "expert":
            errors.append(f"level={params.get('level')}")
        if context.get("ai_content_level") != "expert":
            errors.append("session_level")
    elif action == "set_branch_numbering_decimal":
        if payload.get("action") != "set_branch_numbering":
            errors.append(f"ws={payload.get('action')}")
        if params.get("prefix") != "decimal" or params.get("enabled") is not True:
            errors.append(f"params={params}")
        if diagram_dict.get("_mindmap_branch_numbering_prefix") != "decimal":
            errors.append("session_prefix")
    elif action == "set_branch_numbering_chinese":
        if params.get("prefix") != "chinese" or params.get("enabled") is not True:
            errors.append(f"params={params}")
        if diagram_dict.get("_mindmap_branch_numbering_prefix") != "chinese":
            errors.append("session_prefix")
    elif action == "set_branch_numbering_on":
        if params.get("enabled") is not True:
            errors.append(f"params={params}")
        if diagram_dict.get("_mindmap_branch_numbering") is not True:
            errors.append("session_flag")
    elif action == "set_branch_numbering_off":
        if params.get("enabled") is not False:
            errors.append(f"params={params}")
        if diagram_dict.get("_mindmap_branch_numbering") is not False:
            errors.append("session_flag")
    return errors


def _ok_number_edit(
    action: str,
    command: Dict[str, Any],
    targets: Dict[str, Any],
) -> List[str]:
    errors: List[str] = []
    wanted = targets.get("dotted") if action == "update_node_by_outline" else targets.get("second")
    if not isinstance(wanted, dict):
        errors.append("no_target")
        return errors
    expect_action = "delete_node" if action.startswith("delete_") else "update_node"
    if command.get("action") != expect_action:
        errors.append(f"action={command.get('action')}")
    if str(command.get("node_id") or "") != wanted["node_id"]:
        errors.append(f"node_id={command.get('node_id')} want={wanted['node_id']}")
    if expect_action == "update_node" and command.get("new_text") != "要点提纲":
        errors.append(f"new_text={command.get('new_text')}")
    return errors


async def run_one(
    mmap: RealMindmap,
    action: str,
    template: str,
    *,
    numbering_on: bool,
    targets: Dict[str, Any],
) -> Dict[str, Any]:
    """One new action on a deep-copied session. Does not persist the library row."""
    utterance = _utterance(action, template, targets)
    skip_reason = ""
    if action == "update_node_by_outline" and not targets.get("dotted"):
        skip_reason = "no_dotted_node"
    if action in {"update_node_by_ordinal", "delete_node_by_ordinal"} and not targets.get("second"):
        skip_reason = "no_second_l1"
    if skip_reason or not utterance:
        return {
            "slug": mmap.slug,
            "topic": mmap.topic,
            "action": action,
            "utterance": utterance,
            "ok": False,
            "skipped": True,
            "errors": [skip_reason or "empty_utterance"],
            "outcome": "skipped",
            "reason": skip_reason,
            "loop_action": "",
            "command_action": "",
            "command_node_id": "",
            "ws_action": "",
            "total_ms": 0.0,
        }

    context = copy.deepcopy(mmap.context)
    diagram = context.get("diagram_data")
    if numbering_on and isinstance(diagram, dict):
        diagram["_mindmap_branch_numbering"] = True
    ws = MagicMock()
    vid = create_voice_session(
        user_id="new-action-audit",
        diagram_session_id=f"scope-{mmap.slug}-{action}",
        diagram_type="mindmap",
    )
    voice_sessions[vid]["context"] = context
    voice_sessions[vid]["active_panel"] = "one_sentence"
    bus_mock = AsyncMock(side_effect=lambda *_a, **_k: _applied(action, None))
    ws_mock = AsyncMock(return_value=True)
    errors: List[str] = []
    started = time.perf_counter()

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

    try:
        with (
            patch(
                "services.kitty.agent_loop.loop.llm_service.chat_raw",
                new=AsyncMock(side_effect=AssertionError("LLM should not run")),
            ),
            patch("services.kitty.agent_loop.loop.dispatch_loop_tool", new=_dispatch),
            patch("services.kitty.agent_loop.tools.apply_kitty_legacy_diagram_command", bus_mock),
            patch("services.kitty.agent_loop.tools.send_kitty_ws_action", ws_mock),
            patch("services.kitty.agent_loop.preference_tools.send_kitty_ws_action", ws_mock),
            patch("services.kitty.agent_loop.loop.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.tools.emit_user_ack", new=AsyncMock(return_value=True)),
            patch("services.kitty.agent_loop.preference_tools.emit_user_ack", new=AsyncMock(return_value=True)),
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
                "services.kitty.agent_loop.preference_tools.fanout_voice_command_from_session",
                new=AsyncMock(),
            ),
        ):
            result = await run_typed_agent_loop(ws, vid, utterance, context)
        total_ms = (time.perf_counter() - started) * 1000.0
        live = voice_sessions.get(vid) or {}
        live_ctx = live.get("context") if isinstance(live, dict) else {}
        session_ctx = live_ctx if isinstance(live_ctx, dict) else context
        command: Dict[str, Any] = {}
        payload = _ws_payload(ws_mock)
        if result.outcome != RouteOutcome.EXECUTED:
            errors.append(f"outcome={result.outcome}")
        if action.startswith("set_"):
            if result.reason != "fast_preference":
                errors.append(f"reason={result.reason}")
            if not ws_mock.await_count:
                errors.append("ws_not_called")
            errors.extend(_ok_preference(action, payload, session_ctx))
        else:
            if result.reason != "fast_structural":
                errors.append(f"reason={result.reason}")
            if not bus_mock.await_count:
                errors.append("bus_not_called")
            else:
                command = dict(mock_await_args(bus_mock)[2])
                errors.extend(_ok_number_edit(action, command, targets))
        return {
            "slug": mmap.slug,
            "topic": mmap.topic,
            "action": action,
            "utterance": utterance,
            "ok": not errors,
            "skipped": False,
            "errors": errors,
            "outcome": str(result.outcome),
            "reason": str(result.reason or ""),
            "loop_action": str(result.action or ""),
            "command_action": str(command.get("action") or ""),
            "command_node_id": str(command.get("node_id") or ""),
            "ws_action": str(payload.get("action") or ""),
            "total_ms": round(total_ms, 1),
        }
    except AssertionError as exc:
        return {
            "slug": mmap.slug,
            "topic": mmap.topic,
            "action": action,
            "utterance": utterance,
            "ok": False,
            "skipped": False,
            "errors": [f"AssertionError: {exc}"],
            "outcome": "error",
            "reason": "",
            "loop_action": "",
            "command_action": "",
            "command_node_id": "",
            "ws_action": "",
            "total_ms": round((time.perf_counter() - started) * 1000.0, 1),
        }
    finally:
        voice_sessions.pop(vid, None)


def _print_maps(
    pairs: List[tuple[Dict[str, Any], RealMindmap]],
    targets_by_slug: Dict[str, Dict[str, Any]],
) -> None:
    print("\nPostgres mindmaps")
    print(f"{'#':<3} {'title':<28} {'topic':<18} {'L1#':>4} {'L2+':>4} outline")
    for row, mmap in pairs:
        targets = targets_by_slug[mmap.slug]
        dotted = targets.get("dotted") or {}
        second = targets.get("second") or {}
        mark = dotted.get("no") if isinstance(dotted, dict) else "-"
        second_no = second.get("no") if isinstance(second, dict) else "-"
        print(
            f"{mmap.slug:<3} {str(row['title'])[:27]:<28} {mmap.topic[:17]:<18} "
            f"{targets['l1_count']:>4} {targets['dotted_count']:>4} "
            f"{mark}/{second_no}"
        )


async def _async_main(limit: int) -> int:
    pg_audit = _load_pg_audit()
    mindmap_smoke_helpers_load_dotenv(ROOT / ".env")
    rows = await pg_audit.fetch_pg_mindmaps(limit=max(limit, 16))
    pairs = pg_audit.hydrate_maps(rows)
    if len(pairs) < 10:
        print(f"Need 10 hydratable mindmaps, got {len(pairs)} from {len(rows)} rows")
        return 2
    pairs = pairs[:10]
    targets_by_slug = {mmap.slug: outline_index(mmap.context.get("diagram_data") or {}) for _row, mmap in pairs}
    _print_maps(pairs, targets_by_slug)

    cases: List[Dict[str, Any]] = []
    for _row, mmap in pairs:
        targets = targets_by_slug[mmap.slug]
        for action, template, numbering_on in CASE_SPECS:
            result = await run_one(
                mmap,
                action,
                template,
                numbering_on=numbering_on,
                targets=targets,
            )
            cases.append(result)
            flag = "SKIP" if result.get("skipped") else ("PASS" if result["ok"] else "FAIL")
            print(
                f"[{flag}] {mmap.slug}/{action} reason={result['reason']} "
                f"{result['total_ms']:.0f}ms {result['utterance'][:24]}"
            )
            if result["errors"] and not result.get("skipped"):
                print(f"    {result['errors']}")

    passed = sum(1 for row in cases if row["ok"])
    skipped = sum(1 for row in cases if row.get("skipped"))
    failed = len(cases) - passed - skipped
    report = {
        "maps": [
            {
                "id": row["id"],
                "title": row["title"],
                "slug": mmap.slug,
                "topic": mmap.topic,
                "branch": mmap.branch_label,
                "l1_count": targets_by_slug[mmap.slug]["l1_count"],
                "dotted_count": targets_by_slug[mmap.slug]["dotted_count"],
                "outline": (targets_by_slug[mmap.slug].get("dotted") or {}).get("no"),
                "second": (targets_by_slug[mmap.slug].get("second") or {}).get("no"),
            }
            for row, mmap in pairs
        ],
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "cases": cases,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{passed} passed  {failed} failed  {skipped} skipped  wrote {OUT_JSON}")
    return 0 if failed == 0 else 1


def main() -> int:
    """CLI entry: load env maps and run the new-action audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=16)
    args = parser.parse_args()
    return asyncio.run(_async_main(limit=args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
