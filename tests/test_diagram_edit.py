"""Tests for Diagram Edit Tool core (pending, verify, executor)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.diagram_edit.effects import build_expected_effect, extract_before_fingerprint
from services.diagram_edit.ack import complete_mutation_ack_from_client
from services.diagram_edit.executor import execute_diagram_edit_from_legacy
from services.diagram_edit.pending import (
    MutationAckPayload,
    complete_pending,
    fail_pending_for_scope,
    new_mutation_id,
    register_pending,
    reset_pending_state_for_tests,
    wait_for_ack,
)
from services.diagram_edit.types import DiagramEditCommand, ExpectedEffect
from services.diagram_edit.verify import (
    extract_created_node_id,
    normalize_diagram_text,
    verify_mindmap_effect,
)
from services.kitty.session.runtime_state import voice_sessions


def test_normalize_diagram_text_nfkc() -> None:
    """Text compare uses trim + NFKC."""
    assert normalize_diagram_text("  DIY\u3000") == "DIY"


def test_verify_add_branch_ok() -> None:
    """DIY branch under topic with edge passes verification."""
    effect = ExpectedEffect(
        op="add_branch",
        text="DIY",
        parent_ref="topic",
        checks=["node_exists", "parent_edge_exists"],
    )
    evidence = {
        "nodes": [
            {"id": "topic", "type": "topic", "text": "Cars"},
            {"id": "branch-r-1-0", "text": "DIY"},
        ],
        "connections": [{"source": "topic", "target": "branch-r-1-0"}],
    }
    report = verify_mindmap_effect(effect, evidence, before_node_count=1)
    assert report.ok is True
    assert "node_exists" in report.checks


def test_extract_created_node_id_prefers_ack_list() -> None:
    """Canvas-provided created_node_ids win over evidence text match."""
    effect = ExpectedEffect(op="add_branch", text="DIY", parent_ref="topic")
    evidence = {
        "nodes": [
            {"id": "topic", "type": "topic", "text": "Cars"},
            {"id": "branch-r-1-0", "text": "DIY"},
        ],
        "connections": [{"source": "topic", "target": "branch-r-1-0"}],
    }
    assert (
        extract_created_node_id(
            effect,
            evidence,
            created_node_ids=["branch-r-9-9"],
        )
        == "branch-r-9-9"
    )
    assert extract_created_node_id(effect, evidence) == "branch-r-1-0"


def test_verify_add_branch_missing_edge_fails() -> None:
    """Missing parent edge fails verification."""
    effect = ExpectedEffect(op="add_branch", text="DIY", parent_ref="topic")
    evidence = {
        "nodes": [
            {"id": "topic", "type": "topic", "text": "Cars"},
            {"id": "branch-r-1-0", "text": "DIY"},
        ],
        "connections": [],
    }
    report = verify_mindmap_effect(effect, evidence, before_node_count=1)
    assert report.ok is False


def test_pending_ack_timeout() -> None:
    """Timeout returns None and clears pending entry."""
    reset_pending_state_for_tests()
    mutation_id = new_mutation_id()

    async def run() -> None:
        register_pending(mutation_id, "voice-test")
        result = await wait_for_ack(mutation_id, timeout_sec=0.05)
        assert result is None

    asyncio.run(run())


def test_fail_pending_for_scope_completes_waiter() -> None:
    """Owner disconnect fails in-flight acks for that scope (no ack_timeout wait)."""
    reset_pending_state_for_tests()
    mutation_id = new_mutation_id()

    async def run() -> None:
        fut = register_pending(mutation_id, "voice-mobile", scope="lib-diagram-1")
        n = fail_pending_for_scope(
            "lib-diagram-1",
            error_code="no_owner",
            message="Desktop canvas owner disconnected",
        )
        assert n == 1
        ack = await fut
        assert ack.verified is False
        assert ack.error_code == "no_owner"
        assert fail_pending_for_scope("lib-diagram-1") == 0

    asyncio.run(run())


def test_fail_pending_for_scope_ignores_other_scopes() -> None:
    """Fail-by-scope must not complete pending mutations for a different diagram."""
    reset_pending_state_for_tests()
    mutation_id = new_mutation_id()

    async def run() -> None:
        fut = register_pending(mutation_id, "voice-mobile", scope="lib-a")
        assert fail_pending_for_scope("lib-b") == 0
        assert not fut.done()
        assert complete_pending(MutationAckPayload(mutation_id=mutation_id, verified=True))

    asyncio.run(run())


def test_pending_late_ack_ignored() -> None:
    """Late ack after timeout does not complete a new pending entry."""
    reset_pending_state_for_tests()
    mutation_id = new_mutation_id()

    async def run() -> None:
        register_pending(mutation_id, "voice-test")
        await wait_for_ack(mutation_id, timeout_sec=0.05)
        late = MutationAckPayload(mutation_id=mutation_id, verified=True)
        assert complete_pending(late) is False

    asyncio.run(run())


def test_complete_mutation_ack_from_client() -> None:
    """Inbound WS ack completes pending future."""
    reset_pending_state_for_tests()
    mutation_id = new_mutation_id()

    async def run() -> None:
        fut = register_pending(mutation_id, "voice-test")
        matched = complete_mutation_ack_from_client(
            {
                "mutation_id": mutation_id,
                "verified": True,
                "revision": 3,
                "created_node_ids": ["branch-r-1-0"],
                "evidence": {"nodes": [], "connections": []},
            }
        )
        assert matched is True
        ack = await fut
        assert ack.verified is True
        assert ack.revision == 3
        assert ack.created_node_ids == ["branch-r-1-0"]

    asyncio.run(run())


def test_build_expected_effect_add_branch() -> None:
    """ExpectedEffect for add_node branch under topic."""
    cmd = DiagramEditCommand(
        tool="diagram.add_node",
        args={"text": "DIY"},
        scope="scope-1",
        diagram_type="mindmap",
        legacy_command={"action": "add_node", "target": "DIY"},
    )
    effect = build_expected_effect(cmd, {})
    assert effect.op == "add_branch"
    assert effect.text == "DIY"
    assert effect.parent_ref == "topic"


def test_build_expected_effect_add_child_via_parent_ref() -> None:
    """parent_ref under an existing branch is add_child, not top-level add_branch."""
    cmd = DiagramEditCommand(
        tool="diagram.add_node",
        args={"text": "罗技", "parent_ref": "品牌"},
        scope="scope-1",
        diagram_type="mindmap",
        legacy_command={"action": "add_node", "target": "罗技", "parent_ref": "品牌"},
    )
    effect = build_expected_effect(cmd, {})
    assert effect.op == "add_child"
    assert effect.text == "罗技"
    assert effect.parent_ref == "品牌"


def test_extract_before_fingerprint_nodes() -> None:
    """Fingerprint prefers nodes[] when present."""
    ctx = {
        "diagram_data": {
            "nodes": [{"id": "topic", "text": "A"}],
            "connections": [],
        }
    }
    fp = extract_before_fingerprint(ctx)
    assert len(fp["nodes"]) == 1


@pytest.mark.asyncio
async def test_executor_no_applied_without_verified_ack() -> None:
    """Executor returns ack_timeout when canvas does not ack."""
    reset_pending_state_for_tests()
    ws = MagicMock()
    vid = "voice-test-diagram-edit"
    voice_sessions[vid] = {
        "user_id": "1",
        "diagram_session_id": "scope_edit",
        "diagram_type": "mindmap",
        "_hub_scope_revision": 0,
        "context": {
            "diagram_data": {
                "center": {"text": "Topic"},
                "children": [],
            },
            "one_sentence_phase": "edit",
        },
    }

    try:
        with (
            patch("services.diagram_edit.executor._ensure_handlers"),
            patch(
                "services.diagram_edit.executor.dispatch_tool",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "services.kitty.infra.scope.kitty_scope_access.user_may_access_kitty_scope",
                new=AsyncMock(return_value=True),
            ),
        ):
            result = await execute_diagram_edit_from_legacy(
                ws,
                vid,
                {"action": "add_node", "target": "DIY", "confidence": 0.95},
                dict(voice_sessions[vid]["context"]),
                scope="scope_edit",
                diagram_type="mindmap",
                user_id=1,
                ack_timeout_sec=0.05,
            )
        assert result.status == "failed"
        assert result.error_code == "ack_timeout"
    finally:
        voice_sessions.pop(vid, None)
        reset_pending_state_for_tests()


@pytest.mark.asyncio
async def test_executor_rejects_add_node_without_target() -> None:
    """Verified add_node with empty target must reject — not open palette / ack_timeout."""
    reset_pending_state_for_tests()
    ws = MagicMock()
    vid = "voice-test-empty-target"
    voice_sessions[vid] = {
        "user_id": "1",
        "diagram_session_id": "scope_empty",
        "diagram_type": "mindmap",
        "_hub_scope_revision": 0,
        "context": {
            "diagram_data": {
                "center": {"text": "Topic"},
                "children": [],
            },
            "one_sentence_phase": "edit",
        },
    }

    try:
        with (
            patch("services.diagram_edit.executor._ensure_handlers"),
            patch(
                "services.diagram_edit.executor.dispatch_tool",
                new=AsyncMock(return_value=True),
            ) as dispatch_mock,
            patch(
                "services.kitty.infra.scope.kitty_scope_access.user_may_access_kitty_scope",
                new=AsyncMock(return_value=True),
            ),
        ):
            result = await execute_diagram_edit_from_legacy(
                ws,
                vid,
                {"action": "add_node", "confidence": 0.95},
                dict(voice_sessions[vid]["context"]),
                scope="scope_empty",
                diagram_type="mindmap",
                user_id=1,
                ack_timeout_sec=0.05,
            )
        assert result.status == "rejected"
        assert result.error_code == "not_parsed"
        dispatch_mock.assert_not_awaited()
    finally:
        voice_sessions.pop(vid, None)
        reset_pending_state_for_tests()


@pytest.mark.asyncio
async def test_executor_requires_hub_persist_on_verified_ack() -> None:
    """Verified ack without hub_persist_ok fails with hub_persist_failed."""
    reset_pending_state_for_tests()
    ws = MagicMock()
    vid = "voice-hub-persist-fail"
    voice_sessions[vid] = {
        "user_id": "1",
        "diagram_session_id": "scope_hp",
        "diagram_type": "mindmap",
        "_hub_scope_revision": 1,
        "context": {
            "diagram_data": {
                "center": {"text": "Topic"},
                "children": [],
            },
            "one_sentence_phase": "edit",
        },
    }

    mutation_holder: list[str] = []

    async def fake_dispatch(*_args, **_kwargs) -> bool:
        return True

    def capture_register(mid: str, *_args, **_kwargs):
        mutation_holder.append(mid)
        return register_pending(mid, vid)

    try:
        with (
            patch("services.diagram_edit.executor._ensure_handlers"),
            patch("services.diagram_edit.executor.dispatch_tool", side_effect=fake_dispatch),
            patch(
                "services.kitty.infra.scope.kitty_scope_access.user_may_access_kitty_scope",
                new=AsyncMock(return_value=True),
            ),
            patch("services.diagram_edit.executor.register_pending", side_effect=capture_register),
        ):

            async def run_executor():
                return await execute_diagram_edit_from_legacy(
                    ws,
                    vid,
                    {"action": "add_node", "target": "DIY", "confidence": 0.95},
                    dict(voice_sessions[vid]["context"]),
                    scope="scope_hp",
                    diagram_type="mindmap",
                    user_id=1,
                    ack_timeout_sec=1.0,
                    require_hub_persist=True,
                )

            exec_task = asyncio.create_task(run_executor())
            for _ in range(50):
                if mutation_holder:
                    break
                await asyncio.sleep(0.01)
            assert mutation_holder
            complete_pending(
                MutationAckPayload(
                    mutation_id=mutation_holder[0],
                    verified=True,
                    hub_persist_ok=False,
                    error_code="hub_persist_failed",
                    evidence={
                        "nodes": [
                            {"id": "topic", "type": "topic", "text": "Topic"},
                            {"id": "branch-r-1-0", "text": "DIY"},
                        ],
                        "connections": [{"source": "topic", "target": "branch-r-1-0"}],
                    },
                )
            )
            result = await exec_task
        assert result.status == "failed"
        assert result.error_code == "hub_persist_failed"
    finally:
        voice_sessions.pop(vid, None)
        reset_pending_state_for_tests()
