"""Atomic Redis claim / compare-and-swap for training sessions.

Lua keeps start and steer single-key races off the Python read-modify-write path.
"""

from __future__ import annotations

from typing import Any

from services.features.training.constants import INSTRUCTOR_KEY_PREFIX

CLAIM_ORG_LUA = """
local org_key = KEYS[1]
local inst_key = KEYS[2]
local payload = ARGV[1]
local pointer = ARGV[2]
local ttl = tonumber(ARGV[3])
local now = tonumber(ARGV[4])
local inst_prefix = ARGV[5]
local current = redis.call('GET', org_key)
if current then
  local doc = cjson.decode(current)
  local state = doc['state']
  local expires = tonumber(doc['expires_at']) or 0
  local blocking = (state == 'live' or state == 'paused') and (expires == 0 or expires > now)
  if blocking then
    return 0
  end
  local old_id = doc['instructor_id']
  if old_id then
    redis.call('DEL', inst_prefix .. tostring(old_id))
  end
end
redis.call('SET', org_key, payload, 'EX', ttl)
redis.call('SET', inst_key, pointer, 'EX', ttl)
return 1
"""

CAS_WRITE_LUA = """
local org_key = KEYS[1]
local inst_key = KEYS[2]
local expected = tonumber(ARGV[1])
local payload = ARGV[2]
local pointer = ARGV[3]
local ttl = tonumber(ARGV[4])
local write_pointer = tonumber(ARGV[5])
local current = redis.call('GET', org_key)
if not current then
  return 0
end
local doc = cjson.decode(current)
if tonumber(doc['seq']) ~= expected then
  return 0
end
redis.call('SET', org_key, payload, 'EX', ttl)
if write_pointer == 1 then
  redis.call('SET', inst_key, pointer, 'EX', ttl)
end
return 1
"""


def _as_int(value: Any) -> int:
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    return int(value or 0)


async def claim_org_session(
    redis: Any,
    *,
    org_key: str,
    instructor_key: str,
    payload: str,
    pointer: str,
    ttl: int,
    now: float,
) -> bool:
    """SET the org session only when no unexpired live/paused document exists."""
    won = await redis.eval(
        CLAIM_ORG_LUA,
        2,
        org_key,
        instructor_key,
        payload,
        pointer,
        str(int(ttl)),
        str(float(now)),
        INSTRUCTOR_KEY_PREFIX,
    )
    return _as_int(won) == 1


async def cas_write_session(
    redis: Any,
    *,
    org_key: str,
    instructor_key: str,
    expected_seq: int,
    payload: str,
    pointer: str,
    ttl: int,
    write_pointer: bool,
) -> bool:
    """Replace the org session when ``seq`` still matches ``expected_seq``."""
    won = await redis.eval(
        CAS_WRITE_LUA,
        2,
        org_key,
        instructor_key,
        str(int(expected_seq)),
        payload,
        pointer,
        str(int(ttl)),
        "1" if write_pointer else "0",
    )
    return _as_int(won) == 1
