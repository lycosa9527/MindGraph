"""Organization-scoped cache for identical landing/fresh diagram generations.

Teachers in the same organization who submit a complete-match search
(normalized prompt, language, model, diagram type, instructions) reuse the
first successful spec for ``GEN_RESULT_CACHE_TTL`` seconds (default 2 hours).

Users without ``organization_id`` and RAG requests are never stored.
Autocomplete and canvas-context modes (branch expand, locked topic) share
the cache only when those fields are a complete fingerprint match.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import orjson

from services.diagram.generation_result_coalesce import coalesce_generation
from services.redis import keys as redis_keys
from services.redis.redis_async_client import get_async_redis
from services.redis.redis_client import is_redis_available
from services.utils.error_types import REDIS_ERRORS
from services.utils.typing_helpers import redis_decode

logger = logging.getLogger(__name__)

CACHE_SCHEMA_VERSION = "v2"
STORE_FIELDS = (
    "spec",
    "diagram_type",
    "language",
    "is_learning_sheet",
    "hidden_node_percentage",
    "structure_mode",
    "topics",
    "warning",
    "recovery_warnings",
)
_WHITESPACE_RE = re.compile(r"\s+")


def generation_result_ttl_seconds() -> int:
    """Return configured result TTL. ``0`` disables the cache."""
    return int(redis_keys.TTL_GEN_RESULT)


def generation_result_max_payload_bytes() -> int:
    """Reuse the saved-diagram spec size cap for cached payloads."""
    return int(os.getenv("DIAGRAM_MAX_SPEC_SIZE_KB", "500")) * 1024


def normalize_search_text(value: str | None) -> str:
    """NFC-normalize, strip, and collapse internal whitespace. No case-fold."""
    text = unicodedata.normalize("NFC", value or "")
    return _WHITESPACE_RE.sub(" ", text).strip()


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _positive_org_id(organization_id: Any) -> Optional[int]:
    if isinstance(organization_id, bool):
        return None
    if isinstance(organization_id, int):
        return organization_id if organization_id > 0 else None
    if isinstance(organization_id, str) and organization_id.strip().isdigit():
        parsed = int(organization_id.strip())
        return parsed if parsed > 0 else None
    return None


def is_eligible_for_generation_cache(
    *,
    organization_id: Any,
    request_type: str,
    use_rag: bool = False,
    rag_document_ids: list[Any] | None = None,
) -> bool:
    """True when this request may share a spec with other teachers in the org.

    Autocomplete and canvas-context modes are allowed: those fields go into
    the fingerprint so only a complete match hits. RAG stays out.
    """
    if generation_result_ttl_seconds() <= 0:
        return False
    if _positive_org_id(organization_id) is None:
        return False
    if request_type not in ("diagram_generation", "autocomplete"):
        return False
    return not (use_rag or bool(rag_document_ids))


def fingerprint_generation_request(
    *,
    prompt: str,
    language: str,
    llm: str,
    diagram_type: str | None,
    request_type: str,
    generation_instructions: str | None,
    is_learning_sheet: bool | None,
    dimension_preference: str | None,
    fixed_dimension: str | None = None,
    locked_topic: str | None = None,
    expand_branch: str | None = None,
    mind_map_topic: str | None = None,
    parent_branch: str | None = None,
    concept_a: str | None = None,
    concept_b: str | None = None,
    concept_map_topic: str | None = None,
    link_direction: str | None = None,
    dimension_only_mode: bool | None = None,
    concept_map_relationship_only: bool | None = None,
    existing_analogies: list[Any] | None = None,
    reference_branches: list[Any] | None = None,
    existing_branch_children: list[Any] | None = None,
) -> str:
    """SHA-256 of the canonical complete-match fields (schema ``v2``)."""
    analogies = existing_analogies if isinstance(existing_analogies, list) else []
    payload = {
        "v": CACHE_SCHEMA_VERSION,
        "prompt": normalize_search_text(prompt),
        "language": normalize_search_text(language),
        "llm": normalize_search_text(llm),
        "diagram_type": normalize_search_text(diagram_type) or "auto",
        "request_type": normalize_search_text(request_type) or "diagram_generation",
        "generation_instructions": normalize_search_text(generation_instructions),
        "is_learning_sheet": bool(is_learning_sheet),
        "dimension_preference": normalize_search_text(dimension_preference),
        "fixed_dimension": normalize_search_text(fixed_dimension),
        "locked_topic": normalize_search_text(locked_topic),
        "expand_branch": normalize_search_text(expand_branch),
        "mind_map_topic": normalize_search_text(mind_map_topic),
        "parent_branch": normalize_search_text(parent_branch),
        "concept_a": normalize_search_text(concept_a),
        "concept_b": normalize_search_text(concept_b),
        "concept_map_topic": normalize_search_text(concept_map_topic),
        "link_direction": normalize_search_text(link_direction),
        "dimension_only_mode": bool(dimension_only_mode),
        "concept_map_relationship_only": bool(concept_map_relationship_only),
        "existing_analogies": analogies,
        "reference_branches": [normalize_search_text(item) for item in (reference_branches or []) if _has_text(item)],
        "existing_branch_children": [
            normalize_search_text(item) for item in (existing_branch_children or []) if _has_text(item)
        ],
    }
    encoded = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha256(encoded).hexdigest()


def generation_result_key(org_id: int, fingerprint: str) -> str:
    """Redis key for a cached generation spec."""
    return redis_keys.GEN_RESULT.format(org_id=org_id, fingerprint=fingerprint)


def generation_result_lock_key(org_id: int, fingerprint: str) -> str:
    """Redis SETNX lock key for coalescing concurrent misses."""
    return redis_keys.GEN_RESULT_LOCK.format(org_id=org_id, fingerprint=fingerprint)


def resolve_generation_cache_lookup(prepared: dict[str, Any]) -> Optional[tuple[int, str]]:
    """Return ``(org_id, fingerprint)`` when the prepared request is cacheable."""
    req = prepared.get("req")
    org_id = _positive_org_id(prepared.get("organization_id"))
    if org_id is None or req is None:
        return None
    request_type = str(prepared.get("request_type") or "diagram_generation")
    if not is_eligible_for_generation_cache(
        organization_id=org_id,
        request_type=request_type,
        use_rag=bool(getattr(req, "use_rag", False)),
        rag_document_ids=getattr(req, "rag_document_ids", None),
    ):
        return None
    diagram_type = getattr(req, "diagram_type", None)
    diagram_type_value = getattr(diagram_type, "value", diagram_type)
    if not isinstance(diagram_type_value, str):
        diagram_type_value = None
    fingerprint = fingerprint_generation_request(
        prompt=str(prepared.get("prompt") or ""),
        language=str(prepared.get("language") or ""),
        llm=str(prepared.get("llm_model") or ""),
        diagram_type=diagram_type_value,
        request_type=request_type,
        generation_instructions=prepared.get("generation_instructions"),
        is_learning_sheet=prepared.get("is_learning_sheet"),
        dimension_preference=getattr(req, "dimension_preference", None),
        fixed_dimension=getattr(req, "fixed_dimension", None),
        locked_topic=getattr(req, "locked_topic", None),
        expand_branch=getattr(req, "expand_branch", None),
        mind_map_topic=getattr(req, "mind_map_topic", None),
        parent_branch=getattr(req, "parent_branch", None),
        concept_a=getattr(req, "concept_a", None),
        concept_b=getattr(req, "concept_b", None),
        concept_map_topic=getattr(req, "concept_map_topic", None),
        link_direction=getattr(req, "link_direction", None),
        dimension_only_mode=getattr(req, "dimension_only_mode", None),
        concept_map_relationship_only=getattr(req, "concept_map_relationship_only", None),
        existing_analogies=getattr(req, "existing_analogies", None),
        reference_branches=getattr(req, "reference_branches", None),
        existing_branch_children=getattr(req, "existing_branch_children", None),
    )
    return org_id, fingerprint


def is_cacheable_generation_success(result: dict[str, Any]) -> bool:
    """True when a workflow result is safe to share across the organization."""
    if result.get("success") is False:
        return False
    if _has_text(result.get("error")):
        return False
    spec = result.get("spec")
    if not isinstance(spec, dict) or not spec:
        return False
    diagram_type = result.get("diagram_type")
    return _has_text(diagram_type)


def _payload_from_result(result: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in STORE_FIELDS:
        if field in result:
            payload[field] = result[field]
    return payload


def _result_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"success": True}
    for field in STORE_FIELDS:
        if field in payload:
            result[field] = payload[field]
    return result


async def get_cached_generation_result(org_id: int, fingerprint: str) -> Optional[dict[str, Any]]:
    """Return a shallow-copied cached result, or ``None`` on miss / Redis down."""
    if generation_result_ttl_seconds() <= 0 or not is_redis_available():
        return None
    redis = get_async_redis()
    if redis is None:
        return None
    key = generation_result_key(org_id, fingerprint)
    try:
        raw = redis_decode(await redis.get(key))
    except REDIS_ERRORS as exc:
        logger.debug("[GenResultCache] GET failed for %s: %s", key, exc)
        return None
    if not raw:
        return None
    try:
        decoded = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    result = _result_from_payload(decoded)
    if not is_cacheable_generation_success(result):
        return None
    logger.info(
        "[GenResultCache] hit org=%s fp=%s type=%s",
        org_id,
        fingerprint[:12],
        result.get("diagram_type"),
    )
    return result


async def store_generation_result(org_id: int, fingerprint: str, result: dict[str, Any]) -> bool:
    """Persist a successful spec. Failures, oversize payloads, and Redis errors skip."""
    if generation_result_ttl_seconds() <= 0 or not is_cacheable_generation_success(result):
        return False
    if not is_redis_available():
        return False
    redis = get_async_redis()
    if redis is None:
        return False
    payload = _payload_from_result(result)
    try:
        encoded = orjson.dumps(payload).decode("utf-8")
    except TypeError as exc:
        logger.debug("[GenResultCache] skip store: not JSON-serializable: %s", exc)
        return False
    if len(encoded.encode("utf-8")) > generation_result_max_payload_bytes():
        logger.debug("[GenResultCache] skip store: payload exceeds spec size cap")
        return False
    key = generation_result_key(org_id, fingerprint)
    ttl = generation_result_ttl_seconds()
    try:
        await redis.set(key, encoded, ex=ttl)
    except REDIS_ERRORS as exc:
        logger.debug("[GenResultCache] SET failed for %s: %s", key, exc)
        return False
    logger.info(
        "[GenResultCache] store org=%s fp=%s type=%s ttl=%s",
        org_id,
        fingerprint[:12],
        payload.get("diagram_type"),
        ttl,
    )
    return True


async def load_or_generate_cached_result(
    prepared: dict[str, Any],
    generate: Callable[[], Awaitable[dict[str, Any]]],
    *,
    on_waiting: Callable[[], Awaitable[None]] | None = None,
    on_acquired: Callable[[], Awaitable[None]] | None = None,
    cancel_event: asyncio.Event | None = None,
) -> dict[str, Any]:
    """Return a cached spec or run ``generate`` once per org fingerprint.

    ``skip_cache`` (teacher clicked again after a hit) runs the LLM and does
    not write Redis, so the shared org spec stays the first successful one.
    """
    lookup = resolve_generation_cache_lookup(prepared)
    if lookup is None:
        return await generate()
    org_id, fingerprint = lookup
    skip_cache = bool(getattr(prepared.get("req"), "skip_cache", False))
    if skip_cache:
        result = await generate()
        return {**result, "cached": False}
    cached = await get_cached_generation_result(org_id, fingerprint)
    if cached is not None:
        return {**cached, "cached": True}

    async def loader() -> dict[str, Any]:
        result = await generate()
        await store_generation_result(org_id, fingerprint, result)
        return result

    async def cache_reader() -> Optional[dict[str, Any]]:
        return await get_cached_generation_result(org_id, fingerprint)

    return await coalesce_generation(
        generation_result_lock_key(org_id, fingerprint),
        loader,
        cache_reader,
        on_acquired=on_acquired,
        on_waiting=on_waiting,
        cancel_event=cancel_event,
    )
