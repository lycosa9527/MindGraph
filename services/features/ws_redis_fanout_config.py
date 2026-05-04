"""
Configuration for Redis WebSocket fan-out (multi-worker).

Fan-out topology (Phase 1 fix):
  Pub/sub (PUBLISH / SPUBLISH) is the ONLY delivery path for broadcast.
  XREADGROUP consumer groups are NOT used for broadcast: a group with N
  workers load-balances each entry to exactly ONE worker, which is correct
  for job queues but silently drops ~(N-1)/N of broadcasts — a data-loss bug.

  Redis Streams are retained as an OPTIONAL audit log only (COLLAB_REDIS_STREAMS_AUDIT=1).
  When enabled, XADD runs after PUBLISH in a background task so the audit
  never adds latency to the broadcast hot path.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os

from services.redis.redis_client import is_redis_available

CHAT_FANOUT_CHANNEL = "mg:ws:chat:fanout"
WORKSHOP_FANOUT_CHANNEL = "mg:ws:workshop:fanout"
ENVELOPE_VERSION = 1

WORKSHOP_FANOUT_STREAM_KEY = "mg:ws:workshop:stream"
WORKSHOP_FANOUT_STREAM_MAXLEN = 10_000


def is_ws_fanout_enabled() -> bool:
    """Return True when Redis pub/sub fan-out is enabled."""
    if os.getenv("WS_REDIS_FANOUT_ENABLED", "true").lower() not in (
        "1",
        "true",
        "yes",
    ):
        return False
    try:
        return is_redis_available()
    except ImportError:
        return False


def use_sharded_pubsub() -> bool:
    """
    Return True when SPUBLISH/SSUBSCRIBE should be used.

    Defaults to 1 (enabled) as Phase 3.6: on Redis Cluster it keeps traffic
    slot-local.

    NOTE: On Redis 7.0+ single-node, SPUBLISH and PUBLISH are separate pub/sub
    mechanisms — SPUBLISH only reaches SSUBSCRIBE subscribers, and PUBLISH only
    reaches SUBSCRIBE subscribers.  They do NOT cross-deliver.  The publisher
    and subscriber MUST use the same transport.  Use ``is_sharded_pubsub_active``
    (set by the listener after a successful SSUBSCRIBE) to decide which command
    the publisher should use at runtime.
    """
    return os.getenv("COLLAB_REDIS_SPUBLISH", "1") not in ("0", "false", "False", "")


# Runtime flag: set to True by the listener after a successful SSUBSCRIBE.
# Publisher reads this (via is_sharded_pubsub_active) so both sides always
# use the same transport.  Defaults to False so the publisher falls back to
# plain PUBLISH until the listener confirms sharded pub/sub is live.
_sharded_pubsub_active: bool = False


def is_sharded_pubsub_active() -> bool:
    """Return True only after the listener confirmed SSUBSCRIBE succeeded."""
    return _sharded_pubsub_active


def set_sharded_pubsub_active(value: bool) -> None:
    """Called by the listener to record the actual subscription transport used."""
    global _sharded_pubsub_active  # pylint: disable=global-statement
    _sharded_pubsub_active = value


def use_streams_audit() -> bool:
    """
    Return True when Streams XADD should write an audit copy after pub/sub.

    COLLAB_REDIS_STREAMS_AUDIT replaces the old COLLAB_REDIS_STREAMS_FANOUT.
    The stream is NOT on the broadcast delivery path; it is a durable replay
    log for debugging and audit only.
    """
    return os.getenv(
        "COLLAB_REDIS_STREAMS_AUDIT", "0",
    ) not in ("0", "false", "False", "")
