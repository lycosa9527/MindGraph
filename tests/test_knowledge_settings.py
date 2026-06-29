"""Tests for Knowledge Space settings merge and persistence helpers."""

from __future__ import annotations

from services.knowledge import knowledge_settings as settings


def test_server_defaults_use_config_rerank_threshold(monkeypatch):
    """Server defaults expose deployment config, not hardcoded UI values."""
    monkeypatch.setattr(
        type(settings.config),
        "RERANK_SCORE_THRESHOLD",
        property(lambda _self: 0.5),
    )
    monkeypatch.setattr(
        type(settings.config),
        "CHUNK_SIZE",
        property(lambda _self: 500),
    )
    defaults = settings.server_defaults()
    assert defaults["score_threshold"] == 0.5
    assert defaults["chunk_size"] == 500
    assert defaults["default_method"] == "hybrid"


def test_apply_settings_update_syncs_segmentation_rules():
    """Saving chunk prefs mirrors into rules.segmentation for the chunking pipeline."""
    new_rules, reindex_required = settings.apply_settings_update(
        None,
        default_method="semantic",
        top_k=10,
        score_threshold=0.4,
        chunk_size=600,
        chunk_overlap=80,
    )
    assert reindex_required is True
    assert new_rules["settings"]["retrieval"]["default_method"] == "semantic"
    assert new_rules["rules"]["segmentation"]["max_tokens"] == 600
    assert new_rules["rules"]["segmentation"]["chunk_overlap"] == 80


def test_apply_settings_update_no_reindex_when_chunk_unchanged():
    """Retrieval-only edits do not flag re-index."""
    existing = {
        "settings": {
            "retrieval": {"default_method": "hybrid", "top_k": 5, "score_threshold": 0.5},
            "chunking": {"chunk_size": 500, "chunk_overlap": 50},
        }
    }
    new_rules, reindex_required = settings.apply_settings_update(
        existing,
        default_method="keyword",
        top_k=5,
        score_threshold=0.5,
        chunk_size=500,
        chunk_overlap=50,
    )
    assert reindex_required is False
    assert new_rules["settings"]["retrieval"]["default_method"] == "keyword"


def test_segmentation_from_rules_uses_effective_settings():
    """Chunking pipeline reads merged effective chunk sizes."""
    rules = {
        "settings": {"chunking": {"chunk_size": 640, "chunk_overlap": 64}},
    }
    chunk_size, chunk_overlap = settings.segmentation_from_rules(rules)
    assert chunk_size == 640
    assert chunk_overlap == 64
