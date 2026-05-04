"""
Synthetic monitor: two WebSocket connections to a canary collab URL.

Exit code 0 if both clients complete join -> snapshot -> ping -> update -> leave;
1 otherwise.  Set COLLAB_PROBE_REQUIRE_FULL_CYCLE=0 to keep legacy ping-only
success when the server does not expose a diagram id in probe frames.
Use from cron / k8s probe with env:

  COLLAB_PROBE_WS_URL — full ``ws`` or ``wss`` URL including ``?token=`` if needed
  COLLAB_PROBE_TIMEOUT_S — default 15
  COLLAB_PROBE_DIAGRAM_ID — optional, enables deterministic join/update probe
  COLLAB_PROBE_REQUIRE_FULL_CYCLE — default 1

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any

import websockets
from websockets.exceptions import WebSocketException

logger = logging.getLogger(__name__)


async def _recv_type(
    ws: Any, expected: set[str], timeout: float, max_frames: int = 12,
) -> dict[str, Any] | None:
    for _ in range(max_frames):
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            return None
        if isinstance(payload, dict) and payload.get("type") in expected:
            return payload
    return None


def _probe_update_payload(diagram_id: str, client_name: str) -> dict[str, Any]:
    node_id = os.environ.get("COLLAB_PROBE_NODE_ID", "collab-probe-node")
    return {
        "type": "update",
        "diagram_id": diagram_id,
        "client_op_id": f"synthetic-probe-{client_name}",
        "nodes": [
            {
                "id": node_id,
                "type": "mindMapNode",
                "position": {"x": 0, "y": 0},
                "data": {"label": "synthetic collab probe"},
            }
        ],
    }


async def _one_probe_client(
    url: str,
    timeout: float,
    diagram_id: str | None,
    require_full_cycle: bool,
    client_name: str,
) -> bool:
    payload: Any
    try:
        async with asyncio.timeout(timeout):
            async with websockets.connect(url, max_size=1024 * 1024) as ws:
                join_payload: dict[str, Any] = {"type": "join"}
                if diagram_id:
                    join_payload["diagram_id"] = diagram_id
                await ws.send(json.dumps(join_payload))
                joined = await _recv_type(ws, {"joined"}, timeout)
                if joined is None:
                    return False
                snapshot = await _recv_type(ws, {"snapshot"}, timeout)
                if snapshot is None:
                    return False
                await ws.send(json.dumps({"type": "ping"}))
                payload = await _recv_type(ws, {"pong"}, timeout)
                if payload is None:
                    return False
                target_diagram = diagram_id or str(
                    joined.get("diagram_id") or snapshot.get("diagram_id") or ""
                )
                if not target_diagram:
                    return not require_full_cycle
                await ws.send(
                    json.dumps(_probe_update_payload(target_diagram, client_name))
                )
                ack = await _recv_type(ws, {"update_ack", "error"}, timeout)
                if ack is None or ack.get("type") == "error":
                    if require_full_cycle:
                        return False
                    logger.warning("probe update failed but full cycle is optional")
                await ws.close(code=1000, reason="synthetic_probe_leave")
    except (TimeoutError, OSError):
        logger.warning("probe client failed: timed out or transport error")
        return False
    except WebSocketException as exc:
        logger.warning("probe client failed WebSocket protocol: %s", exc)
        return False
    return True


async def run_dual_collab_ws_probe(
    url: str,
    timeout: float,
    diagram_id: str | None = None,
    require_full_cycle: bool = True,
) -> int:
    """Run exactly two simultaneous probe clients."""
    pair = await asyncio.gather(
        _one_probe_client(url, timeout, diagram_id, require_full_cycle, "a"),
        _one_probe_client(url, timeout, diagram_id, require_full_cycle, "b"),
    )
    return 0 if all(pair) else 1


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "WARNING"))
    parser = argparse.ArgumentParser(description="Canary dual-client collab WS probe")
    parser.add_argument(
        "--url",
        default=os.environ.get("COLLAB_PROBE_WS_URL", ""),
        help="Full WebSocket URL (use env COLLAB_PROBE_WS_URL)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("COLLAB_PROBE_TIMEOUT_S", "15")),
    )
    parser.add_argument(
        "--diagram-id",
        default=os.environ.get("COLLAB_PROBE_DIAGRAM_ID") or None,
    )
    parser.add_argument(
        "--require-full-cycle",
        action="store_true",
        default=os.environ.get("COLLAB_PROBE_REQUIRE_FULL_CYCLE", "1").lower()
        not in ("0", "false", "no"),
        help="Fail unless join, snapshot, update ack, and leave all succeed",
    )
    args = parser.parse_args()
    if not args.url:
        logger.error("COLLAB_PROBE_WS_URL or --url is required")
        sys.exit(2)
    code = asyncio.run(
        run_dual_collab_ws_probe(
            args.url,
            args.timeout,
            args.diagram_id,
            bool(args.require_full_cycle),
        )
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
