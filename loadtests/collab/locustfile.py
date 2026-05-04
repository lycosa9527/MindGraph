"""
Locust harness for MindGraph canvas-collab WebSockets.

Environment
-----------
COLLAB_LOCUST_HOST   Base HTTP URL, e.g. https://staging.example.com (scheme → ws/wss).
COLLAB_JWT           Session JWT (passed as ``?token=…`` — same rule as browsers).
COLLAB_CODES        Comma-separated workshop codes matching WORKSHOP_SIZES expansion.
WORKSHOP_SIZES      Default ``5x100,1x500`` → needs 6 codes: five 100-seat rooms plus one 500-seat.

Needs: ``pip install locust websocket-client``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import os
import random
import time
from typing import List, Mapping, Tuple
from urllib.parse import quote, urlencode, urlparse

try:
    from locust import User, between, events, tag, task  # pylint: disable=import-error
except ImportError:  # pragma: no cover
    raise SystemExit(
        'Install Locust first: pip install locust websocket-client'
    ) from None

try:
    import websocket  # type: ignore  # pip package websocket-client
except ImportError:  # pragma: no cover
    raise SystemExit(
        'Install websocket-client: pip install websocket-client'
    ) from None


DEFAULT_SIZES = '5x100,1x500'


def parse_workshop_sizes(spec: str) -> List[Tuple[int, int]]:
    """Expand ``NxM`` comma-separated tuples into segments."""
    out: List[Tuple[int, int]] = []
    for part in spec.split(','):
        part = part.strip().lower()
        if not part or 'x' not in part:
            continue
        rooms_s, seats_s = part.split('x', 1)
        out.append((int(rooms_s), int(seats_s)))
    return out


def flatten_room_cards(
    layout: List[Tuple[int, int]],
    codes: List[str],
) -> List[Tuple[str, int]]:
    """
    Pair each logical room code with seat weight / capacity notion.

    For Locust weighted selection we only need ``(code, weight)``.
    Weight = seats per-room for sizing probability mass.
    """
    cards: List[Tuple[str, int]] = []
    code_index = 0
    for room_count, seats in layout:
        for _ in range(room_count):
            if code_index >= len(codes):
                raise ValueError(
                    'Not enough COLLAB_CODES for WORKSHOP_SIZES segments'
                )
            cards.append((codes[code_index], seats))
            code_index += 1
    if code_index != len(codes):
        raise ValueError(
            'Too many COLLAB_CODES for WORKSHOP_SIZES — trim extras '
            f'(used {code_index}, got {len(codes)})'
        )
    return cards


def http_base_to_ws_base(http_url: str) -> str:
    parsed = urlparse(http_url.strip())
    scheme = 'wss' if parsed.scheme == 'https' else 'ws'
    if not parsed.hostname:
        raise ValueError(f'Cannot derive WebSocket URL from host {http_url}')
    netloc = parsed.hostname
    if parsed.port:
        netloc = f'{netloc}:{parsed.port}'
    return f'{scheme}://{netloc}'


@events.init.add_listener  # pragma: no cover - locust bootstrap
def _warn_if_missing_env(**_kwargs) -> None:
    if not os.environ.get('COLLAB_JWT'):
        print('[collab locust] WARNING: COLLAB_JWT is unset; connections will fail')
    layout = parse_workshop_sizes(
        os.environ.get('WORKSHOP_SIZES', DEFAULT_SIZES)
    )
    codes = [c.strip() for c in os.environ.get('COLLAB_CODES', '').split(',') if c.strip()]
    try:
        flatten_room_cards(layout, codes)
    except ValueError as exc:
        print(f'[collab locust] WARNING: COLLAB_CODES vs WORKSHOP_SIZES: {exc}')


class CanvasCollabWsUser(User):
    """
    Lightweight workshop participant via raw WebSockets.

    On start each user selects a weighted random room derived from WORKSHOP_SIZES,
    completes the Redis join handshake (`type: join`), then keeps the session
    warm with pings and sporadic benign traffic.
    """

    abstract = False
    host = os.environ.get('COLLAB_LOCUST_HOST', 'http://127.0.0.1:8000')
    wait_time = between(4, 11)

    def _record_ws_request(
        self,
        name: str,
        response_time: float,
        response_length: int,
        exc: BaseException | str | None,
    ) -> None:
        env = getattr(self, 'environment', None)
        hook = getattr(getattr(env, 'events', None), 'request', None)
        if hook is None:
            return
        hook.fire(
            request_type='websocket',
            name=name,
            response_time=response_time,
            response_length=response_length,
            exception=exc,
        )

    def on_start(self) -> None:
        self._jwt = os.environ.get('COLLAB_JWT', '').strip()
        if not self._jwt:
            self._abort_start('COLLAB_JWT unset')
            return
        codes_env = os.environ.get('COLLAB_CODES', '')
        layout = parse_workshop_sizes(
            os.environ.get('WORKSHOP_SIZES', DEFAULT_SIZES)
        )
        codes = [piece.strip().upper() for piece in codes_env.split(',') if piece.strip()]
        if not codes:
            self._abort_start('COLLAB_CODES unset')
            return
        self._room_cards = flatten_room_cards(layout, codes)

        weights = [weight for _, weight in self._room_cards]
        room_code = random.choices(
            [c for c, _ in self._room_cards],
            weights=weights,
            k=1,
        )[0]

        ws_base = http_base_to_ws_base(self.host)
        query = urlencode({'token': self._jwt})
        path_segment = quote(room_code, safe="")
        self._uri = (
            f'{ws_base}/api/ws/canvas-collab/{path_segment}?{query}'
        )

        self._sock: websocket.WebSocket | None = None
        try:
            self._sock = websocket.create_connection(self._uri, timeout=45)
            self._sock.send(json.dumps({'type': 'join'}))
        except (OSError, ValueError, websocket.WebSocketException) as exc:
            self._abort_start(str(exc))

    def _abort_start(self, reason: str) -> None:
        """Mark failure via Locust without raising (keeps swarm alive)."""
        self._record_ws_request(
            name='/api/ws/canvas-collab/…',
            response_time=0.0,
            response_length=0,
            exc=reason,
        )

    def on_stop(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except (OSError, websocket.WebSocketException):
                pass
            self._sock = None

    @tag('collab', 'heartbeat')
    @task(weight=10)
    def workshop_ping(self) -> None:
        if not self._sock:
            return
        payload = {'type': 'ping'}
        self._send_named('ping', payload)

    @tag('collab', 'presence')
    @task(weight=1)
    def node_selection_probe(self) -> None:
        if not self._sock:
            return
        probe = {'type': 'node_selected', 'node_id': 'locust_probe', 'selected': False}
        self._send_named('node_selected', probe)

    def _send_named(self, logical_name: str, payload: Mapping[str, object]) -> None:
        """Send WS frame while recording latency in Locust UI."""
        if not self._sock:
            return
        raw = json.dumps(payload, separators=(',', ':'))
        started = time.perf_counter()
        try:
            self._sock.send(raw)
            self._record_ws_request(
                name=f'WS::{logical_name}',
                response_time=max(1.0, (time.perf_counter() - started) * 1000.0),
                response_length=len(raw),
                exc=None,
            )
        except (OSError, websocket.WebSocketException) as exc:
            self._record_ws_request(
                name=f'WS::{logical_name}',
                response_time=(time.perf_counter() - started) * 1000.0,
                response_length=0,
                exc=exc,
            )
