"""Unit tests for organization-scoped generation result cache."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock

import orjson
import pytest

from services.diagram import generation_result_cache as cache_mod
from services.diagram.generation_result_cache import (
    fingerprint_generation_request,
    generation_result_key,
    is_cacheable_generation_success,
    is_eligible_for_generation_cache,
    normalize_search_text,
    resolve_generation_cache_lookup,
)


def _fingerprint(**overrides: Any) -> str:
    fields: dict[str, Any] = {
        "prompt": "光合作用",
        "language": "zh",
        "llm": "qwen",
        "diagram_type": None,
        "request_type": "diagram_generation",
        "generation_instructions": None,
        "is_learning_sheet": False,
        "dimension_preference": None,
    }
    fields.update(overrides)
    return fingerprint_generation_request(**fields)


def test_normalize_search_text_nfc_strip_collapse() -> None:
    """Complete-match normalization is NFC + strip + collapse, not case-fold."""
    assert normalize_search_text("  e\u0301  ") == "é"
    assert normalize_search_text("  光合作用  ") == "光合作用"
    assert normalize_search_text("aaa   bbb") == "aaa bbb"
    assert normalize_search_text("AAA") == "AAA"


def test_fingerprint_matches_equivalent_prompts() -> None:
    """Whitespace-equivalent topics share a fingerprint."""
    left = _fingerprint(prompt="  光合作用  ")
    right = _fingerprint(prompt="光合作用")
    assert left == right
    assert len(left) == 64


def test_fingerprint_differs_on_language_model_type_instructions() -> None:
    """Language, model, forced type, and instructions are part of the match."""
    base = _fingerprint()
    assert _fingerprint(language="en") != base
    assert _fingerprint(llm="deepseek") != base
    assert _fingerprint(diagram_type="bubble_map") != base
    assert _fingerprint(generation_instructions="小学") != base
    assert _fingerprint(is_learning_sheet=True) != base
    assert _fingerprint(fixed_dimension="按季节") != base


def test_fingerprint_differs_on_autocomplete_context() -> None:
    """Autocomplete and canvas-context fields are part of the v2 match."""
    base = _fingerprint()
    assert _fingerprint(request_type="autocomplete") != base
    assert _fingerprint(locked_topic="主题") != base
    assert _fingerprint(expand_branch="分支") != base
    assert _fingerprint(mind_map_topic="中心") != base
    assert _fingerprint(parent_branch="上级") != base
    assert _fingerprint(concept_a="A") != base
    assert _fingerprint(concept_map_topic="主题") != base
    assert _fingerprint(link_direction="both") != base
    assert _fingerprint(existing_analogies=[{"left": "日", "right": "月"}]) != base
    assert _fingerprint(reference_branches=["甲"]) != base
    assert _fingerprint(existing_branch_children=["子"]) != base


def test_eligibility_rejects_non_org_and_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    """No org, TTL 0, and RAG stay out; autocomplete may cache."""
    monkeypatch.setattr(cache_mod, "generation_result_ttl_seconds", lambda: 7200)
    base = {
        "organization_id": 7,
        "request_type": "diagram_generation",
    }
    assert is_eligible_for_generation_cache(**base) is True
    assert is_eligible_for_generation_cache(organization_id=None, request_type="diagram_generation") is False
    assert is_eligible_for_generation_cache(organization_id=0, request_type="diagram_generation") is False
    assert is_eligible_for_generation_cache(organization_id=7, request_type="autocomplete") is True
    assert is_eligible_for_generation_cache(**base, use_rag=True) is False
    assert is_eligible_for_generation_cache(**base, rag_document_ids=[1]) is False
    assert is_eligible_for_generation_cache(organization_id="7", request_type="diagram_generation") is True
    monkeypatch.setattr(cache_mod, "generation_result_ttl_seconds", lambda: 0)
    assert is_eligible_for_generation_cache(**base) is False


def test_org_isolation_uses_distinct_keys() -> None:
    """School A and school B never share a Redis key."""
    fingerprint = _fingerprint()
    assert generation_result_key(1, fingerprint) != generation_result_key(2, fingerprint)
    assert generation_result_key(1, fingerprint).startswith("gen:result:1:")


def test_resolve_lookup_skips_when_ineligible() -> None:
    """RAG requests do not produce a cache lookup."""
    req = SimpleNamespace(
        use_rag=True,
        rag_document_ids=None,
        expand_branch=None,
        locked_topic=None,
        dimension_only_mode=None,
        concept_map_relationship_only=None,
        mind_map_topic=None,
        existing_analogies=None,
        diagram_type=None,
        dimension_preference=None,
    )
    prepared = {
        "req": req,
        "organization_id": 3,
        "request_type": "diagram_generation",
        "prompt": "aaa",
        "language": "zh",
        "llm_model": "qwen",
        "generation_instructions": None,
        "is_learning_sheet": False,
    }
    assert resolve_generation_cache_lookup(prepared) is None


def test_resolve_lookup_autocomplete_includes_locked_topic() -> None:
    """Same-org autocomplete shares a key only when canvas context matches."""
    req = SimpleNamespace(
        use_rag=False,
        rag_document_ids=None,
        expand_branch=None,
        locked_topic="主题",
        dimension_only_mode=None,
        concept_map_relationship_only=None,
        mind_map_topic=None,
        existing_analogies=None,
        diagram_type=None,
        dimension_preference=None,
        parent_branch=None,
        reference_branches=None,
        existing_branch_children=None,
        concept_a=None,
        concept_b=None,
        fixed_dimension=None,
    )
    other = SimpleNamespace(**{**req.__dict__, "locked_topic": "别的主题"})
    prepared = {
        "req": req,
        "organization_id": 3,
        "request_type": "autocomplete",
        "prompt": "aaa",
        "language": "zh",
        "llm_model": "qwen",
        "generation_instructions": None,
        "is_learning_sheet": False,
    }
    left = resolve_generation_cache_lookup(prepared)
    right = resolve_generation_cache_lookup({**prepared, "req": other})
    assert left is not None and right is not None
    assert left[0] == 3
    assert left[1] != right[1]


def test_resolve_lookup_same_org_same_fingerprint() -> None:
    """Two teachers in one org with the same search share a fingerprint."""
    req = SimpleNamespace(
        use_rag=False,
        rag_document_ids=None,
        expand_branch=None,
        locked_topic=None,
        dimension_only_mode=None,
        concept_map_relationship_only=None,
        mind_map_topic=None,
        existing_analogies=None,
        diagram_type=None,
        dimension_preference=None,
    )
    first = {
        "req": req,
        "organization_id": 9,
        "request_type": "diagram_generation",
        "prompt": "aaa",
        "language": "zh",
        "llm_model": "qwen",
        "generation_instructions": None,
        "is_learning_sheet": False,
    }
    second = dict(first)
    left = resolve_generation_cache_lookup(first)
    right = resolve_generation_cache_lookup(second)
    assert left is not None and right is not None
    assert left == right
    assert left[0] == 9


def test_is_cacheable_generation_success() -> None:
    """Failures and content-filter outcomes are never stored."""
    assert is_cacheable_generation_success({"success": True, "spec": {"topic": "a"}, "diagram_type": "mind_map"})
    assert not is_cacheable_generation_success({"success": False, "spec": {"topic": "a"}, "diagram_type": "mind_map"})
    assert not is_cacheable_generation_success(
        {"success": True, "spec": {"topic": "a"}, "diagram_type": "mind_map", "error": "filtered"}
    )
    assert not is_cacheable_generation_success({"success": True, "spec": {}, "diagram_type": "mind_map"})


@pytest.mark.asyncio
async def test_store_skips_failure_and_oversize(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failed results and oversized payloads do not write Redis."""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    monkeypatch.setattr(cache_mod, "is_redis_available", lambda: True)
    monkeypatch.setattr(cache_mod, "get_async_redis", lambda: redis)
    monkeypatch.setattr(cache_mod, "generation_result_ttl_seconds", lambda: 7200)
    monkeypatch.setattr(cache_mod, "generation_result_max_payload_bytes", lambda: 16)

    failed = await cache_mod.store_generation_result(
        1,
        "abc",
        {"success": False, "spec": {"topic": "a"}, "diagram_type": "mind_map"},
    )
    assert failed is False
    redis.set.assert_not_awaited()

    huge = await cache_mod.store_generation_result(
        1,
        "abc",
        {"success": True, "spec": {"topic": "x" * 100}, "diagram_type": "mind_map"},
    )
    assert huge is False
    redis.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_store_and_get_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful specs round-trip without request_id or thinking_coins."""
    stored: dict[str, str] = {}

    class _Redis:
        async def set(self, key: str, value: str, ex: int | None = None) -> bool:
            """Capture SET payload and assert the 2-hour TTL."""
            stored[key] = value
            assert ex == 7200
            assert isinstance(value, str)
            return True

        async def get(self, key: str) -> Optional[str]:
            """Return the UTF-8 JSON string previously written by set."""
            return stored.get(key)

    redis = _Redis()
    monkeypatch.setattr(cache_mod, "is_redis_available", lambda: True)
    monkeypatch.setattr(cache_mod, "get_async_redis", lambda: redis)
    monkeypatch.setattr(cache_mod, "generation_result_ttl_seconds", lambda: 7200)

    result = {
        "success": True,
        "spec": {"topic": "aaa"},
        "diagram_type": "mind_map",
        "language": "zh",
        "request_id": "gen_old",
        "thinking_coins": {"balance": 9},
    }
    assert await cache_mod.store_generation_result(4, "fp1", result) is True
    cached = await cache_mod.get_cached_generation_result(4, "fp1")
    assert cached is not None
    assert cached["spec"] == {"topic": "aaa"}
    assert cached["success"] is True
    assert "request_id" not in cached
    assert "thinking_coins" not in cached
    payload = orjson.loads(stored[generation_result_key(4, "fp1")])
    assert "request_id" not in payload


@pytest.mark.asyncio
async def test_load_or_generate_returns_cache_without_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """A complete-match lookup serves Redis and never calls generate()."""
    cached = {"success": True, "spec": {"topic": "aaa"}, "diagram_type": "mind_map"}
    generate = AsyncMock(return_value={"success": True, "spec": {"topic": "fresh"}})
    monkeypatch.setattr(cache_mod, "resolve_generation_cache_lookup", lambda _prepared: (8, "fp"))
    monkeypatch.setattr(cache_mod, "get_cached_generation_result", AsyncMock(return_value=cached))
    result = await cache_mod.load_or_generate_cached_result({"organization_id": 8}, generate)
    assert result["spec"] == cached["spec"]
    assert result["cached"] is True
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_skip_cache_regenerates_without_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """A refresh after a hit runs the LLM and leaves the shared org spec untouched."""
    generate = AsyncMock(return_value={"success": True, "spec": {"topic": "fresh"}, "diagram_type": "mind_map"})
    store = AsyncMock(return_value=True)
    getter = AsyncMock(return_value={"success": True, "spec": {"topic": "old"}, "diagram_type": "mind_map"})
    coalesce = AsyncMock()
    monkeypatch.setattr(cache_mod, "resolve_generation_cache_lookup", lambda _prepared: (8, "fp"))
    monkeypatch.setattr(cache_mod, "get_cached_generation_result", getter)
    monkeypatch.setattr(cache_mod, "store_generation_result", store)
    monkeypatch.setattr(cache_mod, "coalesce_generation", coalesce)
    req = SimpleNamespace(skip_cache=True)
    result = await cache_mod.load_or_generate_cached_result({"organization_id": 8, "req": req}, generate)
    assert result["spec"] == {"topic": "fresh"}
    assert result.get("cached") is False
    generate.assert_awaited_once()
    getter.assert_not_awaited()
    store.assert_not_awaited()
    coalesce.assert_not_awaited()
