"""
Redis-backed active editor state for diagram workshop (multi-worker).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Tuple

from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)

_TTL_SECONDS = 86400


def _key(code: str) -> str:
    return f"mg:ws:workshop:editors:{code}"


async def load_editors(code: str) -> Dict[str, Dict[int, str]]:
    """Load node_id -> {user_id: username} from Redis."""
    try:
        r = get_async_redis()
        if not r:
            return {}
        raw = await r.get(_key(code))
        if not raw:
            return {}
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        out: Dict[str, Dict[int, str]] = {}
        for nid, editors in parsed.items():
            if not isinstance(editors, dict):
                continue
            inner: Dict[int, str] = {}
            for uid_s, name in editors.items():
                try:
                    inner[int(uid_s)] = str(name)
                except (ValueError, TypeError):
                    continue
            out[str(nid)] = inner
        return out
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("[WorkshopEditorsRedis] load failed: %s", exc)
        return {}


async def save_editors(code: str, editors: Dict[str, Dict[int, str]]) -> None:
    """Persist editor map; delete key if empty."""
    try:
        r = get_async_redis()
        if not r:
            return
        key = _key(code)
        if not editors:
            await r.delete(key)
            return
        serializable: Dict[str, Dict[str, str]] = {}
        for nid, ed in editors.items():
            serializable[str(nid)] = {str(uid): name for uid, name in ed.items()}
        await r.setex(key, _TTL_SECONDS, json.dumps(serializable, ensure_ascii=False))
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("[WorkshopEditorsRedis] save failed: %s", exc)


async def remove_user_from_all_nodes(
    code: str,
    user_id: int,
    editors: Dict[str, Dict[int, str]],
) -> Tuple[Dict[str, Dict[int, str]], bool]:
    """Remove user_id from every node; return updated dict and whether changed."""
    changed = False
    nodes_to_drop: list[str] = []
    for nid, ed in list(editors.items()):
        if user_id in ed:
            ed.pop(user_id, None)
            changed = True
        if not ed:
            nodes_to_drop.append(nid)
    for nid in nodes_to_drop:
        del editors[nid]
    if changed:
        await save_editors(code, editors)
    return editors, changed
