"""
Synthetic monitor: two WebSocket connections to a canary collab URL.

Exit code 0 if both clients receive a JSON frame after ping; 1 otherwise.
Use from cron / k8s probe with env:

  COLLAB_PROBE_WS_URL — full ``ws`` or ``wss`` URL including ``?token=`` if needed
  COLLAB_PROBE_TIMEOUT_S — default 15

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


async def _one_probe_client(url: str, timeout: float) -> bool:
    payload: Any
    raw: Any
    try:
        async with asyncio.timeout(timeout):
            async with websockets.connect(url, max_size=1024 * 1024) as ws:
                await ws.send(json.dumps({"type": "ping"}))
                raw = await ws.recv()
    except (TimeoutError, OSError):
        logger.warning("probe client failed: timed out or transport error")
        return False
    except WebSocketException as exc:
        logger.warning("probe client failed WebSocket protocol: %s", exc)
        return False
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("type") is not None


async def run_dual_collab_ws_probe(url: str, timeout: float) -> int:
    """Run exactly two simultaneous probe clients."""
    pair = await asyncio.gather(
        _one_probe_client(url, timeout),
        _one_probe_client(url, timeout),
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
    args = parser.parse_args()
    if not args.url:
        logger.error("COLLAB_PROBE_WS_URL or --url is required")
        sys.exit(2)
    code = asyncio.run(run_dual_collab_ws_probe(args.url, args.timeout))
    sys.exit(code)


if __name__ == "__main__":
    main()
