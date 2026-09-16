"""Unit tests for the generic organization-scoped LLM result cache."""

from __future__ import annotations

from typing import Optional
from unittest.mock import AsyncMock

import pytest

from services.llm import org_result_cache as cache_mod
from services.llm.org_result_cache import (
    fingerprint_org_payload,
    normalize_org_cache_list,
    normalize_org_cache_text,
    org_llm_result_key,
    positive_org_id,
)


def test_normalize_org_cache_text_and_list() -> None:
    """NFC, strip, collapse; drop blank list items."""
    assert normalize_org_cache_text("  e\u0301  ") == "é"
    assert normalize_org_cache_text("aaa   bbb") == "aaa bbb"
    assert normalize_org_cache_list([" 甲 ", "", "乙"]) == ["甲", "乙"]
    assert not normalize_org_cache_list("not-a-list")


def test_positive_org_id() -> None:
    """Only positive ints (or digit strings) are cacheable orgs."""
    assert positive_org_id(9) == 9
    assert positive_org_id("12") == 12
    assert positive_org_id(0) is None
    assert positive_org_id(None) is None
    assert positive_org_id(True) is None


def test_fingerprint_stable_and_sensitive() -> None:
    """Same payload matches; language or extra fields change the key."""
    left = fingerprint_org_payload({"text": "光合作用", "lang": "zh"})
    right = fingerprint_org_payload({"lang": "zh", "text": "光合作用"})
    assert left == right
    assert len(left) == 64
    assert fingerprint_org_payload({"text": "光合作用", "lang": "en"}) != left


def test_org_isolation_uses_namespace_and_org() -> None:
    """Translate vs explain, and school A vs B, never share a Redis key."""
    fingerprint = fingerprint_org_payload({"text": "a"})
    assert org_llm_result_key("translate", 1, fingerprint) != org_llm_result_key("node_explain", 1, fingerprint)
    assert org_llm_result_key("translate", 1, fingerprint) != org_llm_result_key("translate", 2, fingerprint)


@pytest.mark.asyncio
async def test_store_and_get_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful JSON objects round-trip with the shared TTL."""
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
    monkeypatch.setattr(cache_mod, "org_llm_ttl_seconds", lambda: 7200)

    payload = {"text": "Photosynthesis", "events": [{"event": "image", "images": ["u"]}]}
    assert await cache_mod.store_org_llm_result("translate", 4, "fp1", payload) is True
    cached = await cache_mod.get_org_llm_result("translate", 4, "fp1")
    assert cached == payload


@pytest.mark.asyncio
async def test_store_skips_empty_and_oversize(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty and oversized payloads do not write Redis."""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    monkeypatch.setattr(cache_mod, "is_redis_available", lambda: True)
    monkeypatch.setattr(cache_mod, "get_async_redis", lambda: redis)
    monkeypatch.setattr(cache_mod, "org_llm_ttl_seconds", lambda: 7200)
    monkeypatch.setattr(cache_mod, "org_llm_max_payload_bytes", lambda: 16)

    assert await cache_mod.store_org_llm_result("translate", 1, "fp", {}) is False
    assert await cache_mod.store_org_llm_result("translate", 1, "fp", {"text": "x" * 100}) is False
    redis.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_or_generate_returns_cache_without_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """A complete-match lookup serves Redis and never calls generate()."""
    cached = {"text": "cached"}
    generate = AsyncMock(return_value={"text": "fresh"})
    monkeypatch.setattr(cache_mod, "positive_org_id", lambda _org: 8)
    monkeypatch.setattr(cache_mod, "org_llm_ttl_seconds", lambda: 7200)
    monkeypatch.setattr(cache_mod, "get_org_llm_result", AsyncMock(return_value=cached))
    result = await cache_mod.load_or_generate_org_llm_result("translate", 8, {"text": "a"}, generate)
    assert result == cached
    generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_or_generate_skips_cache_without_org(monkeypatch: pytest.MonkeyPatch) -> None:
    """Teachers without an organization always run generate()."""
    generate = AsyncMock(return_value={"text": "fresh"})
    getter = AsyncMock(return_value={"text": "cached"})
    monkeypatch.setattr(cache_mod, "get_org_llm_result", getter)
    result = await cache_mod.load_or_generate_org_llm_result(
        "translate",
        None,
        {"text": "a"},
        generate,
    )
    assert result == {"text": "fresh"}
    generate.assert_awaited_once()
    getter.assert_not_awaited()
