"""Contract tests for the dual-client collab WebSocket probe (no staging required)."""

from __future__ import annotations

from unittest import mock

import pytest


@pytest.mark.asyncio
async def test_run_dual_collab_ws_probe_reports_success(monkeypatch):
    import scripts.collab_synthetic_probe as probe

    class _Sock:
        async def send(self, _: str) -> None:
            return None

        async def recv(self) -> str:
            return '{"type":"pong"}'

    class _Ctx:
        async def __aenter__(self) -> _Sock:
            return _Sock()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb

    fake_mod = mock.MagicMock()
    fake_mod.connect = lambda *_a, **_k: _Ctx()
    monkeypatch.setattr(probe, 'websockets', fake_mod)

    outcome = await probe.run_dual_collab_ws_probe(
        'wss://example.invalid/ws?token=jwt',
        5,
    )

    assert outcome == 0


@pytest.mark.asyncio
async def test_run_dual_reports_failure_when_frame_has_no_type(monkeypatch):
    import scripts.collab_synthetic_probe as probe

    class _Sock:
        async def send(self, _: str) -> None:
            return None

        async def recv(self) -> str:
            return '{"ghost":true}'

    class _Ctx:
        async def __aenter__(self) -> _Sock:
            return _Sock()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb

    fake_mod = mock.MagicMock()
    fake_mod.connect = lambda *_a, **_k: _Ctx()
    monkeypatch.setattr(probe, 'websockets', fake_mod)

    outcome = await probe.run_dual_collab_ws_probe(
        'wss://example.invalid/ws?token=jwt',
        5,
    )

    assert outcome == 1
