"""
Async helpers that offload large JSON serialisation / deserialisation and
deep-copy to a thread pool when the payload exceeds a configurable byte
threshold.

For small payloads (the common case) the functions call json.dumps / json.loads
/ copy.deepcopy synchronously on the event loop — the overhead of scheduling
a thread pool task would outweigh any benefit.  Only payloads above
``COLLAB_JSON_THREAD_OFFLOAD_BYTES`` (default 64 KiB) are offloaded.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
from typing import Any, Dict, Optional

_OFFLOAD_THRESHOLD = int(os.getenv("COLLAB_JSON_THREAD_OFFLOAD_BYTES", str(64 * 1024)))


def _offload_threshold() -> int:
    return _OFFLOAD_THRESHOLD


async def dumps_maybe_offload(
    obj: Any,
    *,
    ensure_ascii: bool = False,
) -> str:
    """
    Serialise *obj* to a JSON string.

    Offloads to ``asyncio.to_thread`` when the object is a dict/list whose
    rough size (estimated from a small pre-check) suggests the serialised form
    will exceed ``COLLAB_JSON_THREAD_OFFLOAD_BYTES``.  Falls back to inline
    serialisation on any error.
    """
    if isinstance(obj, (dict, list)) and _should_offload_dict(obj):
        try:
            return await asyncio.to_thread(json.dumps, obj, ensure_ascii=ensure_ascii)
        except (TypeError, ValueError, OSError, RuntimeError):
            pass
    return json.dumps(obj, ensure_ascii=ensure_ascii)


async def loads_maybe_offload(raw: str) -> Any:
    """
    Deserialise a JSON string.

    Offloads to ``asyncio.to_thread`` when ``len(raw)`` exceeds
    ``COLLAB_JSON_THREAD_OFFLOAD_BYTES``.
    """
    if len(raw) > _OFFLOAD_THRESHOLD:
        try:
            return await asyncio.to_thread(json.loads, raw)
        except (TypeError, ValueError, OSError, RuntimeError):
            pass
    return json.loads(raw)


async def deepcopy_maybe_offload(obj: Any, estimated_bytes: Optional[int] = None) -> Any:
    """
    Deep-copy *obj*.

    Offloads to ``asyncio.to_thread`` when *estimated_bytes* is given and
    exceeds the threshold, or when the object is a large dict/list.
    """
    if estimated_bytes is not None and estimated_bytes > _OFFLOAD_THRESHOLD:
        try:
            return await asyncio.to_thread(copy.deepcopy, obj)
        except (TypeError, OSError, RuntimeError, MemoryError):
            pass
    elif isinstance(obj, (dict, list)) and _should_offload_dict(obj):
        try:
            return await asyncio.to_thread(copy.deepcopy, obj)
        except (TypeError, OSError, RuntimeError, MemoryError):
            pass
    return copy.deepcopy(obj)


def _should_offload_dict(obj: Any) -> bool:
    """
    Cheap heuristic: walk only the top level of a dict/list to estimate size.

    We avoid a full ``json.dumps`` just to check — that would defeat the purpose.
    A rough upper bound is ``len(str(obj))``.  When in doubt, inline is faster
    for small objects.
    """
    try:
        if isinstance(obj, dict):
            total = sum(len(str(k)) + len(str(v)) for k, v in obj.items())
        elif isinstance(obj, list):
            total = sum(len(str(item)) for item in obj[:200])
        else:
            return False
        return total > _OFFLOAD_THRESHOLD
    except (TypeError, ValueError, AttributeError):
        return False


def apply_live_spec_deepcopy(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous deep-copy of a live-spec document.

    Call this inside ``asyncio.to_thread`` for large documents; or use
    ``deepcopy_maybe_offload`` for the async path.
    """
    return copy.deepcopy(doc)
