"""Unit tests for workshop WS Redis fan-out publish, PG fallback, listener dispatch."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from redis.exceptions import RedisError


def _truthy() -> bool:
    return True


def _falsy_audit() -> bool:
    return False


def _any_redis_client() -> object:
    return object()


@pytest.fixture(autouse=True)
def _reset_fanout_delivery_state():
    """Ensure module-level fan-out LRU / connection buckets start clean."""
    from services.features.workshop_ws_fanout_delivery import ACTIVE_CONNECTIONS
    from services.features import workshop_ws_fanout_delivery as wfd

    wfd._RECENT_FANOUT_IDS.clear()
    ACTIVE_CONNECTIONS.clear()
    yield
    wfd._RECENT_FANOUT_IDS.clear()
    ACTIVE_CONNECTIONS.clear()


@pytest.mark.asyncio
async def test_envelope_publish_injects_msg_id(monkeypatch):
    """Workshop payloads without msg_id gain one before Redis transport."""
    from services.features import ws_redis_fanout_publish as pub

    recorded: Dict[str, str] = {}

    async def spy_transport(_client: Any, channel: str, body: str) -> None:
        recorded['channel'] = channel
        recorded['body'] = body

    monkeypatch.setattr(pub, '_publish_with_channel_transport', spy_transport)
    monkeypatch.setattr(pub, 'get_async_redis', _any_redis_client)
    monkeypatch.setattr(pub, 'is_ws_fanout_enabled', _truthy)
    monkeypatch.setattr(pub, 'use_streams_audit', _falsy_audit)

    envelope = {
        'v': 1,
        'k': 'ws',
        'code': 'ABC-XYZ',
        'mode': 'all',
        'd': json.dumps({'type': 'presence', 'x': 1}, ensure_ascii=False),
    }

    await pub.publish_workshop_fanout_async(envelope)

    outer = json.loads(recorded['body'])
    inner = json.loads(outer['d'])
    assert isinstance(inner.get('msg_id'), str)
    assert inner['msg_id']


@pytest.mark.asyncio
async def test_publish_redis_error_schedules_pg_with_same_payload(monkeypatch):
    """Redis failures enqueue PG NOTIFY with enriched envelope (still has msg_id)."""
    from services.features import ws_redis_fanout_publish as pub

    captured: List[Dict[str, Any]] = []

    async def spy_publish_pg(env: Dict[str, Any]) -> None:
        captured.append(dict(env))

    async def flaky(_cli: Any, _ch: str, _bod: str) -> None:
        raise RedisError('simulated outage')

    monkeypatch.setattr(pub, '_publish_with_channel_transport', flaky)
    monkeypatch.setattr(pub, 'publish_pg_notify_fanout_async', spy_publish_pg)
    monkeypatch.setattr(pub, 'get_async_redis', _any_redis_client)
    monkeypatch.setattr(pub, 'is_ws_fanout_enabled', _truthy)
    monkeypatch.setattr(pub, 'use_streams_audit', _falsy_audit)

    envelope = {
        'v': 1,
        'k': 'ws',
        'code': 'ROOM-1',
        'mode': 'others',
        'ex': 9,
        'd': json.dumps({'seq': 1, 'hello': True}, ensure_ascii=False),
    }
    await pub.publish_workshop_fanout_async(envelope)
    await asyncio.sleep(0)

    assert captured
    inner = json.loads(captured[0]['d'])
    assert isinstance(inner.get('msg_id'), str)


@pytest.mark.asyncio
async def test_handle_workshop_raw_dispatches_deliver(monkeypatch):
    """Listener path forwards decoded envelopes."""
    from services.features import ws_redis_fanout_listener as lst

    calls: List[tuple[str, str, int | None, str]] = []

    async def fake_deliver(code: str, mode: str, exclude: int | None, data_str: str) -> None:
        calls.append((code, mode, exclude, data_str))

    def record_received() -> None:
        return None

    monkeypatch.setattr(lst, 'deliver_local_workshop_broadcast', fake_deliver)
    monkeypatch.setattr(lst, 'record_ws_fanout_workshop_received', record_received)

    payload_obj = {
        'v': 1,
        'k': 'ws',
        'code': 'ROOM-XYZ',
        'mode': 'others',
        'ex': 5,
        'd': json.dumps({'seq': 2}, ensure_ascii=False),
    }
    await lst._handle_workshop_raw(json.dumps(payload_obj))

    assert len(calls) == 1
    code, mode, exclude, blob = calls[0]
    assert code == 'ROOM-XYZ'
    assert mode == 'others'
    assert exclude == 5
    assert json.loads(blob)['seq'] == 2


@pytest.mark.asyncio
async def test_pg_notify_warns_on_oversized_payload(monkeypatch):
    """Oversized pg_notify payloads are dropped before touching the database."""
    from services.features import ws_pg_notify_fanout as pgn

    monkeypatch.setenv('COLLAB_PG_NOTIFY_FALLBACK', '1')
    lines: List[str] = []

    def capture(msg: str, *_a: object, **_k: object) -> None:
        lines.append(str(msg))

    monkeypatch.setattr(pgn.logger, 'warning', capture)
    oversized = {'v': 1, 'k': 'ws', 'code': 'c', 'mode': 'all', 'd': 'z' * 9000}

    await pgn.publish_pg_notify_fanout_async(oversized)

    assert lines and any('too large' in entry for entry in lines)


@pytest.mark.asyncio
async def test_deliver_local_drop_second_identical_msg_id(monkeypatch):
    """LRU remembers msg_id across deliveries and suppresses repeats."""
    from services.features.workshop_ws_fanout_delivery import ACTIVE_CONNECTIONS
    from services.features import workshop_ws_fanout_delivery as wfd

    pushes: List[int] = []

    async def counting_push_shard(*_args: object, **_kwargs: object) -> None:
        pushes.append(1)

    monkeypatch.setattr(wfd, '_push_shard', counting_push_shard)

    def record_shards(_n: int) -> None:
        return None

    monkeypatch.setattr(wfd, 'record_ws_broadcast_shards', record_shards)

    async def noop_record_latency(_ms: float) -> None:
        return None

    monkeypatch.setattr(wfd, '_record_broadcast_latency', noop_record_latency)

    queue: asyncio.Queue[object] = asyncio.Queue()
    dummy = SimpleNamespace(send_queue=queue, qsize_high_water=0)

    ACTIVE_CONNECTIONS['Z'] = {1: dummy}
    frame = json.dumps({'type': 'x', 'msg_id': 'dupid', 'v': 1})

    await wfd.deliver_local_workshop_broadcast('Z', 'all', None, frame)
    await wfd.deliver_local_workshop_broadcast('Z', 'all', None, frame)

    assert len(pushes) == 1
