"""Shared COS env-root prefix: {env}/{module}."""

from __future__ import annotations

import pytest

from config.cos_env_prefix import (
    cos_app_identity,
    cos_env_root,
    cos_feature_prefix,
    cos_production_tree_enabled,
    uses_live_production_prefixes,
)
from config.settings import config
from services.infrastructure.lifecycle.cos_prefix_posture import log_cos_prefix_posture


def test_cos_env_root_maps_environment() -> None:
    """ENVIRONMENT becomes a single folder name."""
    assert cos_env_root("production") == "production"
    assert cos_env_root("prod") == "production"
    assert cos_env_root("test") == "test"
    assert cos_env_root("development") == "dev"
    assert cos_env_root("dev") == "dev"
    assert cos_env_root("staging") == "staging"


def test_cos_env_prefix_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """COS_ENV_PREFIX replaces the env root for every module."""
    monkeypatch.setenv("COS_ENV_PREFIX", "e2e-smoke")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert cos_env_root() == "e2e-smoke"
    assert cos_feature_prefix("workshop") == "e2e-smoke/workshop"
    assert cos_feature_prefix("backups") == "e2e-smoke/backups"


def test_all_modules_share_env_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Workshop, documents, backups, showcase live under the same env folder."""
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert cos_feature_prefix("workshop") == "dev/workshop"
    assert cos_feature_prefix("documents") == "dev/documents"
    assert cos_feature_prefix("backups") == "dev/backups"
    assert cos_feature_prefix("showcase") == "dev/showcase"
    assert cos_feature_prefix("zhihui") == "dev/zhihui"
    assert cos_feature_prefix("training") == "dev/training"
    assert cos_feature_prefix("temp_images") == "dev/temp_images"


def test_legacy_app_identity_still_maps() -> None:
    """Old module-first identity helper stays for existing bucket keys."""
    assert cos_app_identity("production") == "mindgraph"
    assert cos_app_identity("test") == "mindgraph-Test"
    assert cos_app_identity("development") == "mindgraph-Dev"


def test_config_prefixes_follow_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset COS_*_PREFIX values resolve to {env}/{module}."""
    for key in (
        "COS_ENV_PREFIX",
        "COS_DOCUMENTS_PREFIX",
        "COS_SHOWCASE_PREFIX",
        "COS_ZHIHUI_PREFIX",
        "COS_TEMP_IMAGES_PREFIX",
        "COS_TRAINING_PREFIX",
        "COS_WORKSHOP_PREFIX",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    config.refresh_env_cache()
    try:
        assert config.COS_DOCUMENTS_PREFIX == "dev/documents"
        assert config.COS_SHOWCASE_PREFIX == "dev/showcase"
        assert config.COS_ZHIHUI_PREFIX == "dev/zhihui"
        assert config.COS_TEMP_IMAGES_PREFIX == "dev/temp_images"
        assert config.COS_TRAINING_PREFIX == "dev/training"
        assert config.COS_WORKSHOP_PREFIX == "dev/workshop"
        monkeypatch.setenv("ENVIRONMENT", "test")
        config.refresh_env_cache()
        assert config.COS_DOCUMENTS_PREFIX == "test/documents"
        assert config.COS_SHOWCASE_PREFIX == "test/showcase"
    finally:
        config.refresh_env_cache()


def test_production_keeps_live_prefixes_until_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ENVIRONMENT=production does not create a production/ tree by default."""
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    config.refresh_env_cache()
    try:
        assert uses_live_production_prefixes() is True
        assert cos_production_tree_enabled() is False
        assert cos_feature_prefix("documents") == "documents/mindgraph"
        assert cos_feature_prefix("showcase") == "showcase/mindgraph"
        assert cos_feature_prefix("zhihui") == "zhihui/mindgraph"
        assert cos_feature_prefix("temp_images") == "temp_images/mindgraph"
        assert cos_feature_prefix("training") == "training/mindgraph"
        assert cos_feature_prefix("workshop") == "workshop/mindgraph"
        assert cos_feature_prefix("backups") == "backups/mindgraph"
        assert not cos_feature_prefix("documents").startswith("production/")
    finally:
        config.refresh_env_cache()


def test_production_tree_is_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """COS_ENV_PREFIX=production is the only way onto production/{module}."""
    monkeypatch.setenv("COS_ENV_PREFIX", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    config.refresh_env_cache()
    try:
        assert cos_production_tree_enabled() is True
        assert uses_live_production_prefixes() is False
        assert cos_feature_prefix("documents") == "production/documents"
        assert cos_feature_prefix("training") == "production/training"
    finally:
        config.refresh_env_cache()


def test_cos_prefix_posture_logs_without_error() -> None:
    """Startup prefix dump must not raise."""
    log_cos_prefix_posture()
