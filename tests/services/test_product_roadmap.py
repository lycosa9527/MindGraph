"""Shared COS product roadmap parsing."""

from __future__ import annotations

import json

import pytest
from fastapi.routing import APIRoute

from routers.core.product_roadmap import router
from services.features.roadmap.product_roadmap import (
    ROADMAP_OBJECT_KEY,
    clear_product_roadmap_cache,
    load_product_roadmap,
    parse_product_roadmap,
    save_product_roadmap,
)


def test_roadmap_key_is_outside_env_prefixes() -> None:
    """The roadmap object sits in shared/, not dev/, test/, or production/."""
    assert ROADMAP_OBJECT_KEY == "shared/roadmap/product_roadmap.json"
    assert not ROADMAP_OBJECT_KEY.startswith(("dev/", "test/", "production/"))


def test_parse_keeps_known_columns_and_skips_junk() -> None:
    """Unknown columns, English-only cards, and non-objects are dropped."""
    raw = json.dumps(
        {
            "updated_at": "2026-11-22",
            "items": [
                {
                    "column": "now",
                    "title": "正在做",
                    "summary": "一句话",
                    "owner": "Roy",
                    "area": "画布",
                    "target": "2026年12月",
                },
                {"column": "nope", "title": "丢弃"},
                "not-an-object",
                {"column": "shipped", "title_en": "Shipped"},
            ],
        }
    ).encode()
    parsed = parse_product_roadmap(raw)
    assert parsed["updated_at"] == "2026-11-22"
    assert [item["column"] for item in parsed["items"]] == ["now"]
    assert parsed["items"][0]["owner"] == "Roy"
    assert parsed["items"][0]["area"] == "画布"
    assert parsed["items"][0]["target"] == "2026年12月"
    assert "title_en" not in parsed["items"][0]


def test_target_keeps_only_a_chinese_year_month() -> None:
    """Free-text times and the old English time are dropped."""
    raw = json.dumps(
        {
            "items": [
                {
                    "column": "now",
                    "title": "甲",
                    "target": "2026年12月",
                    "target_en": "December",
                },
                {"column": "next", "title": "乙", "target": "12月"},
                {"column": "later", "title": "丙", "target": "December"},
            ]
        }
    ).encode()
    parsed = parse_product_roadmap(raw)
    assert parsed["items"][0]["target"] == "2026年12月"
    assert "title_en" not in parsed["items"][0]
    assert "summary_en" not in parsed["items"][0]
    assert "area_en" not in parsed["items"][0]
    assert parsed["items"][1]["target"] == ""
    assert parsed["items"][2]["target"] == ""


def test_parse_rejects_invalid_json() -> None:
    """A broken file is an error, not an empty board."""
    with pytest.raises(ValueError):
        parse_product_roadmap(b"not-json")


def test_load_reads_the_shared_key_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """The loader asks COS for the shared key once, then reuses the copy."""
    clear_product_roadmap_cache()
    calls: list[str] = []

    def _fake_get(key: str, **_kwargs: object) -> bytes:
        calls.append(key)
        return b'{"updated_at":"2026-11-22","items":[{"column":"next","title":"Next"}]}'

    monkeypatch.setattr(
        "services.features.roadmap.product_roadmap.get_object_bytes",
        _fake_get,
    )
    first = load_product_roadmap()
    second = load_product_roadmap()
    assert calls == [ROADMAP_OBJECT_KEY]
    assert first["items"][0]["title"] == "Next"
    assert second == first
    clear_product_roadmap_cache()


def test_load_missing_object_is_an_empty_board(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing object opens an empty board instead of an error."""
    clear_product_roadmap_cache()

    def _missing(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(
        "services.features.roadmap.product_roadmap.get_object_bytes",
        _missing,
    )
    assert load_product_roadmap() == {"updated_at": "", "items": []}
    clear_product_roadmap_cache()


def test_save_writes_the_shared_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid save replaces the shared object and the next read uses that copy."""
    clear_product_roadmap_cache()
    uploaded_key = ""
    uploaded_body = b""

    def _upload(data: bytes, key: str, **_kwargs: object) -> bool:
        nonlocal uploaded_key, uploaded_body
        uploaded_key = key
        uploaded_body = data
        return True

    monkeypatch.setattr(
        "services.features.roadmap.product_roadmap.upload_bytes",
        _upload,
    )
    saved = save_product_roadmap([{"column": "now", "title": "正在做", "summary": "一句话"}])
    assert uploaded_key == ROADMAP_OBJECT_KEY
    assert "正在做".encode() in uploaded_body
    assert saved["updated_at"]
    assert load_product_roadmap()["items"][0]["title"] == "正在做"
    clear_product_roadmap_cache()


def test_save_rejects_a_blank_card() -> None:
    """A card with no title is refused and nothing is uploaded."""
    with pytest.raises(ValueError):
        save_product_roadmap([{"column": "now", "title": "  "}])


def test_put_route_is_superadmin_only() -> None:
    """Reading stays open. Replacing the file depends on require_superadmin."""

    def dependency_names(method: str) -> list[str]:
        route = next(
            item
            for item in router.routes
            if isinstance(item, APIRoute) and item.methods is not None and method in item.methods
        )
        names: list[str] = []
        for dep in route.dependant.dependencies:
            name = getattr(dep.call, "__name__", "")
            if isinstance(name, str) and name:
                names.append(name)
        return names

    put_calls = dependency_names("PUT")
    get_calls = dependency_names("GET")
    assert "require_superadmin" in put_calls
    assert "require_superadmin" not in get_calls
