"""Atomic Redis Lua for multi-device session store + FIFO eviction.

The script also writes the per-device eviction fence and kick notice in the
same EVAL as the SREM, so an in-flight /refresh cannot re-admit a kicked
device before Python side-effects run.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from services.redis import keys as redis_keys
from services.utils.typing_helpers import redis_decode_required

# Returned instead of evicted entries when refresh is blocked by the fence.
DEVICE_KICKED_SENTINEL = "__device_kicked__"
FIFO_KICK_REASON = "max_devices_exceeded"

# KEYS[1]  session set key
# ARGV[1]  new token entry  "timestamp:device_hash:token_hash"
# ARGV[2]  session TTL (seconds)
# ARGV[3]  max concurrent sessions
# ARGV[4]  device hash (empty string when not provided)
# ARGV[5]  current time (float as string)
# ARGV[6]  evicted-device key prefix  "session:evicted_device:{user_id}:"
# ARGV[7]  kick-notice key prefix     "session_invalidated:{user_id}:"
# ARGV[8]  kick-notice JSON
# ARGV[9]  admit evicted device ("1" login, "0" refresh)
# Returns  evicted session entries, or {DEVICE_KICKED_SENTINEL}
STORE_SESSION_LUA = """
local key           = KEYS[1]
local entry         = ARGV[1]
local ttl           = tonumber(ARGV[2])
local max_s         = tonumber(ARGV[3])
local dev           = ARGV[4]
local now           = tonumber(ARGV[5])
local evict_prefix  = ARGV[6]
local notice_prefix = ARGV[7]
local notice_json   = ARGV[8]
local admit         = ARGV[9]
local kick_reason   = 'max_devices_exceeded'

-- 1. Remove expired (stale) sessions.
local all = redis.call('SMEMBERS', key)
for _, e in ipairs(all) do
    local c = string.find(e, ':')
    if c then
        local ts = tonumber(string.sub(e, 1, c - 1))
        if ts and (now - ts) > ttl then
            redis.call('SREM', key, e)
        end
    end
end

-- 2. Refresh must not re-enter after FIFO/manual kick. Login may.
if dev ~= '' and evict_prefix ~= '' then
    if redis.call('EXISTS', evict_prefix .. dev) == 1 then
        if admit ~= '1' then
            return {'__device_kicked__'}
        end
        redis.call('DEL', evict_prefix .. dev)
    end
end

-- 3. Revoke any existing session from the same device.
if dev ~= '' then
    local rem = redis.call('SMEMBERS', key)
    for _, e in ipairs(rem) do
        local c1 = string.find(e, ':')
        if c1 then
            local rest = string.sub(e, c1 + 1)
            local c2   = string.find(rest, ':')
            local edev = c2 and string.sub(rest, 1, c2 - 1) or rest
            if edev == dev then
                redis.call('SREM', key, e)
            end
        end
    end
end

-- 4. Add new token and refresh TTL.
redis.call('SADD',   key, entry)
redis.call('EXPIRE', key, ttl)

-- 5. Evict oldest sessions when over the limit.
-- Never evict the entry just added (new device always keeps the slot).
-- Must match select_oldest_sessions_to_evict().
if (not max_s) or max_s < 1 then
    max_s = 1
end
local count   = redis.call('SCARD', key)
local evicted = {}
if count > max_s then
    local cur = redis.call('SMEMBERS', key)
    table.sort(cur, function(a, b)
        local ca = string.find(a, ':')
        local cb = string.find(b, ':')
        local ta = ca and tonumber(string.sub(a, 1, ca - 1)) or 0
        local tb = cb and tonumber(string.sub(b, 1, cb - 1)) or 0
        if ta == tb then
            if a == entry then return false end
            if b == entry then return true end
        end
        return ta < tb
    end)
    local to_remove = count - max_s
    local removed = 0
    for i = 1, #cur do
        if removed >= to_remove then
            break
        end
        if cur[i] and cur[i] ~= entry then
            local ev = cur[i]
            redis.call('SREM', key, ev)
            evicted[#evicted + 1] = ev
            removed = removed + 1
            local c1 = string.find(ev, ':')
            if c1 then
                local rest = string.sub(ev, c1 + 1)
                local c2 = string.find(rest, ':')
                if c2 then
                    local edev = string.sub(rest, 1, c2 - 1)
                    local ehash = string.sub(rest, c2 + 1)
                    if edev ~= '' and evict_prefix ~= '' then
                        redis.call('SET', evict_prefix .. edev, kick_reason, 'EX', ttl)
                    end
                    if ehash ~= '' and notice_prefix ~= '' and notice_json ~= '' then
                        redis.call('SET', notice_prefix .. ehash, notice_json, 'EX', ttl)
                    end
                end
            end
        end
    end
end

return evicted
"""


def evicted_device_key_prefix(user_id: int) -> str:
    """Prefix for ``session:evicted_device:{user_id}:{device_hash}``."""
    return redis_keys.SESSION_EVICTED_DEVICE.format(user_id=user_id, device_hash="")


def invalidation_notice_key_prefix(user_id: int) -> str:
    """Prefix for ``session_invalidated:{user_id}:{token_hash}``."""
    return redis_keys.SESSION_INVALIDATED.format(user_id=user_id, token_hash="")


def is_device_kicked_eval_result(raw: object) -> bool:
    """True when EVAL refused to store because the device is fenced."""
    if raw is None:
        return False
    if isinstance(raw, (bytes, str)):
        return redis_decode_required(raw) == DEVICE_KICKED_SENTINEL
    if isinstance(raw, (list, tuple)) and len(raw) == 1:
        item = raw[0]
        if isinstance(item, (bytes, str)):
            return redis_decode_required(item) == DEVICE_KICKED_SENTINEL
    return False
