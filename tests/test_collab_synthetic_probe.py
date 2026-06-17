"""Contract tests for the dual-client collab WebSocket probe (no staging required)."""

from __future__ import annotations

from unittest import mock

import pytest

import scripts.collab_synthetic_probe as probe


@pytest.mark.asyncio
async def test_run_dual_collab_ws_probe_reports_success(monkeypatch):
    """Test run dual collab ws probe reports success."""

    class _Sock:
        def __init__(self) -> None:
            """init  ."""
            self.frames = [
                '{"type":"joined","diagram_id":"diag-1"}',
                '{"type":"snapshot","diagram_id":"diag-1","spec":{}}',
                '{"type":"pong"}',
                '{"type":"update_ack","client_op_id":"synthetic-probe"}',
            ]
            self.closed = False

        async def send(self, _: str) -> None:
            """Send."""
            return None

        async def recv(self) -> str:
            """Recv."""
            return self.frames.pop(0)

        async def close(self, *, code: int, reason: str) -> None:
            """Close."""
            self.closed = code == 1000 and bool(reason)

    class _Ctx:
        async def __aenter__(self) -> _Sock:
            """aenter  ."""
            return _Sock()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            """aexit  ."""
            del exc_type, exc, tb

    fake_mod = mock.MagicMock()
    fake_mod.connect = lambda *_a, **_k: _Ctx()
    monkeypatch.setattr(probe, "websockets", fake_mod)

    outcome = await probe.run_dual_collab_ws_probe(
        "wss://example.invalid/ws?token=jwt",
        5,
        diagram_id="diag-1",
    )

    assert outcome == 0


@pytest.mark.asyncio
async def test_run_dual_reports_failure_when_frame_has_no_type(monkeypatch):
    """Test run dual reports failure when frame has no type."""

    class _Sock:
        async def send(self, _: str) -> None:
            """Send."""
            return None

        async def recv(self) -> str:
            """Recv."""
            return '{"ghost":true}'

    class _Ctx:
        async def __aenter__(self) -> _Sock:
            """aenter  ."""
            return _Sock()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            """aexit  ."""
            del exc_type, exc, tb

    fake_mod = mock.MagicMock()
    fake_mod.connect = lambda *_a, **_k: _Ctx()
    monkeypatch.setattr(probe, "websockets", fake_mod)

    outcome = await probe.run_dual_collab_ws_probe(
        "wss://example.invalid/ws?token=jwt",
        5,
        require_full_cycle=False,
    )

    assert outcome == 1
