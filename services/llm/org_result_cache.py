"""Generic organization-scoped Redis cache for exact-match LLM tool results.

Used by translate, concept-map focus, prompt-to-diagram, and node explain.
Landing ``generate_graph`` keeps its own module and key prefix.

TTL follows ``GEN_RESULT_CACHE_TTL`` (default 2 hours; ``0`` disables).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import orjson

from services.diagram.generation_result_coalesce import coalesce_generation
from services.llm.org_custom_config import org_custom_llm_cache_stamp
from services.llm.org_custom_llm_constants import API_TYPE_PLATFORM
from services.redis import keys as redis_keys
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import REDIS_ERRORS
from services.utils.typing_helpers import redis_decode

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")
SCHEMA_VERSION = "v1"


def org_llm_ttl_seconds() -> int:
    """Shared TTL with the generation result cache."""
    return int(redis_keys.TTL_GEN_RESULT)


def org_llm_max_payload_bytes() -> int:
    """Reuse the saved-diagram spec size cap."""
    return int(os.getenv("DIAGRAM_MAX_SPEC_SIZE_KB", "500")) * 1024


def normalize_org_cache_text(value: Any) -> str:
    """NFC-normalize, strip, and collapse internal whitespace. No case-fold."""
    text = unicodedata.normalize("NFC", str(value or ""))
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_org_cache_list(values: Any) -> list[str]:
    """Normalize a list of labels for fingerprinting."""
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = normalize_org_cache_text(item)
        if text:
            out.append(text)
    return out


def positive_org_id(organization_id: Any) -> Optional[int]:
    """Return a positive int org id, or None."""
    if isinstance(organization_id, bool):
        return None
    if isinstance(organization_id, int):
        return organization_id if organization_id > 0 else None
    if isinstance(organization_id, str) and organization_id.strip().isdigit():
        parsed = int(organization_id.strip())
        return parsed if parsed > 0 else None
    return None


def fingerprint_org_payload(payload: dict[str, Any]) -> str:
    """SHA-256 of a canonical JSON object."""
    body = {"v": SCHEMA_VERSION, **payload}
    encoded = orjson.dumps(body, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha256(encoded).hexdigest()


def org_llm_result_key(namespace: str, org_id: int, fingerprint: str) -> str:
    """Redis value key."""
    return redis_keys.ORG_LLM_RESULT.format(ns=namespace, org_id=org_id, fingerprint=fingerprint)


def org_llm_lock_key(namespace: str, org_id: int, fingerprint: str) -> str:
    """Redis SETNX lock key."""
    return redis_keys.ORG_LLM_LOCK.format(ns=namespace, org_id=org_id, fingerprint=fingerprint)


async def get_org_llm_result(namespace: str, org_id: int, fingerprint: str) -> Optional[dict[str, Any]]:
    """Return a cached JSON object, or None."""
    if org_llm_ttl_seconds() <= 0 or not is_redis_available():
        return None
    redis = get_async_redis()
    if redis is None:
        return None
    key = org_llm_result_key(namespace, org_id, fingerprint)
    try:
        raw = redis_decode(await redis.get(key))
    except REDIS_ERRORS as exc:
        logger.debug("[OrgLLMCache] GET failed for %s: %s", key, exc)
        return None
    if not raw:
        return None
    try:
        decoded = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    logger.info("[OrgLLMCache] hit ns=%s org=%s fp=%s", namespace, org_id, fingerprint[:12])
    return decoded


async def store_org_llm_result(
    namespace: str,
    org_id: int,
    fingerprint: str,
    payload: dict[str, Any],
) -> bool:
    """Persist a JSON object. Fail-open on Redis or oversize."""
    if org_llm_ttl_seconds() <= 0 or not isinstance(payload, dict) or not payload:
        return False
    if not is_redis_available():
        return False
    redis = get_async_redis()
    if redis is None:
        return False
    try:
        encoded = orjson.dumps(payload).decode("utf-8")
    except TypeError as exc:
        logger.debug("[OrgLLMCache] skip store ns=%s: %s", namespace, exc)
        return False
    if len(encoded.encode("utf-8")) > org_llm_max_payload_bytes():
        logger.debug("[OrgLLMCache] skip store ns=%s: payload too large", namespace)
        return False
    key = org_llm_result_key(namespace, org_id, fingerprint)
    ttl = org_llm_ttl_seconds()
    try:
        await redis.set(key, encoded, ex=ttl)
    except REDIS_ERRORS as exc:
        logger.debug("[OrgLLMCache] SET failed for %s: %s", key, exc)
        return False
    logger.info("[OrgLLMCache] store ns=%s org=%s fp=%s ttl=%s", namespace, org_id, fingerprint[:12], ttl)
    return True


async def load_or_generate_org_llm_result(
    namespace: str,
    organization_id: Any,
    payload: dict[str, Any],
    generate: Callable[[], Awaitable[Optional[dict[str, Any]]]],
) -> Optional[dict[str, Any]]:
    """Return a cached object or run ``generate`` once per org fingerprint."""
    org_id = positive_org_id(organization_id)
    if org_id is None or org_llm_ttl_seconds() <= 0:
        return await generate()
    try:
        stamp = await org_custom_llm_cache_stamp(org_id)
    except BACKGROUND_INFRA_ERRORS:
        stamp = API_TYPE_PLATFORM
    stamped = {**payload, "custom_llm": stamp}
    fingerprint = fingerprint_org_payload(stamped)
    cached = await get_org_llm_result(namespace, org_id, fingerprint)
    if cached is not None:
        return cached

    async def loader() -> Optional[dict[str, Any]]:
        result = await generate()
        if isinstance(result, dict) and result:
            await store_org_llm_result(namespace, org_id, fingerprint, result)
        return result

    async def reader() -> Optional[dict[str, Any]]:
        return await get_org_llm_result(namespace, org_id, fingerprint)

    return await coalesce_generation(
        org_llm_lock_key(namespace, org_id, fingerprint),
        loader,
        reader,
    )
