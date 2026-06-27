"""Redis-backed for OAuth CSRF state tokens."""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from typing import Any, Optional

from redis.exceptions import RedisError

from services.auth.oauth.oauth_constants import OAUTH_STATE_PREFIX, OAUTH_STATE_TTL_SECONDS
from services.redis.redis_async_client import get_async_redis
from services.utils.error_types import REDIS_ERRORS

logger = logging.getLogger(__name__)

_LUA_CONSUME_STATE = """
local val = redis.call('GET', KEYS[1])
if not val then
  return false
end
redis.call('DEL', KEYS[1])
return val
"""


@dataclass(frozen=True)
class OauthStatePayload:
    """Parsed OAuth state stored in Redis."""

    organization_id: int
    provider: str
    mode: str
    user_id: Optional[int] = None
    use_corp_scope: bool = False


def _state_key(state: str) -> str:
    return f"{OAUTH_STATE_PREFIX}{state}"


async def mint_oauth_state(
    *,
    organization_id: int,
    provider: str,
    mode: str,
    user_id: Optional[int] = None,
    use_corp_scope: bool = False,
) -> str:
    """Create one-time OAuth state token and store payload in Redis."""
    redis = get_async_redis()
    if redis is None:
        raise RuntimeError("redis_unavailable")
    state = secrets.token_urlsafe(32)
    payload: dict[str, Any] = {
        "organization_id": int(organization_id),
        "provider": (provider or "").strip().lower(),
        "mode": (mode or "").strip().lower(),
        "user_id": int(user_id) if user_id is not None else None,
        "use_corp_scope": bool(use_corp_scope),
    }
    key = _state_key(state)
    try:
        ok = await redis.set(key, json.dumps(payload), ex=OAUTH_STATE_TTL_SECONDS, nx=True)
        if not ok:
            return await mint_oauth_state(
                organization_id=organization_id,
                provider=provider,
                mode=mode,
                user_id=user_id,
                use_corp_scope=use_corp_scope,
            )
    except REDIS_ERRORS as exc:
        logger.error("OAuth state mint failed: %s", exc)
        raise RuntimeError("oauth_state_mint_failed") from exc
    return state


async def consume_oauth_state(state: str) -> Optional[OauthStatePayload]:
    """Validate and consume state (one-time)."""
    stripped = (state or "").strip()
    if not stripped:
        return None
    redis = get_async_redis()
    if redis is None:
        return None
    key = _state_key(stripped)
    try:
        raw = await redis.eval(_LUA_CONSUME_STATE, 1, key)
    except RedisError as exc:
        logger.warning("OAuth state consume redis error: %s", exc)
        return None
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    org_id = data.get("organization_id")
    provider = data.get("provider")
    mode = data.get("mode")
    if not isinstance(org_id, int) or not provider or not mode:
        return None
    user_id = data.get("user_id")
    uid = int(user_id) if isinstance(user_id, int) and user_id > 0 else None
    return OauthStatePayload(
        organization_id=int(org_id),
        provider=str(provider),
        mode=str(mode),
        user_id=uid,
        use_corp_scope=bool(data.get("use_corp_scope")),
    )
