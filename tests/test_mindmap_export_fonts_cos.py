"""Unit tests for mind-map export font COS helpers."""

from __future__ import annotations

import pytest

from services.infrastructure.sync.cos_sync_env import (
    mindmap_export_font_cos_key,
    mindmap_export_fonts_meta_cos_key,
    mindmap_export_fonts_rel_prefix,
)
from services.infrastructure.sync.mindmap_export_fonts_cos import (
    FONT_FILES,
    is_allowed_mindmap_export_font,
)


def test_font_allowlist() -> None:
    """Only NotoSansSC TTF basenames are served for PDF embedding."""
    assert is_allowed_mindmap_export_font("NotoSansSC-Regular.ttf")
    assert is_allowed_mindmap_export_font("NotoSansSC-Bold.ttf")
    assert not is_allowed_mindmap_export_font("evil.ttf")
    assert not is_allowed_mindmap_export_font("../NotoSansSC-Regular.ttf")
    assert not is_allowed_mindmap_export_font("NotoSansCJKsc-Regular.otf")


def test_cos_keys_under_sync_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """COS object keys stay under the shared sync/fonts/mindmap-export prefix."""
    monkeypatch.setenv("COS_SYNC_KEY_PREFIX", "backups/mindgraph-shared")
    assert mindmap_export_fonts_rel_prefix() == "sync/fonts/mindmap-export"
    assert mindmap_export_font_cos_key("NotoSansSC-Regular.ttf") == (
        "backups/mindgraph-shared/sync/fonts/mindmap-export/NotoSansSC-Regular.ttf"
    )
    assert mindmap_export_fonts_meta_cos_key().endswith("/sync/fonts/mindmap-export/meta.json")


def test_cos_key_rejects_path_traversal() -> None:
    """Path segments in font names must not escape the COS prefix."""
    with pytest.raises(ValueError):
        mindmap_export_font_cos_key("../secret.ttf")


def test_font_files_tuple_stable() -> None:
    """Regular and Bold NotoSansSC TTF remain the published pair."""
    assert "NotoSansSC-Regular.ttf" in FONT_FILES
    assert "NotoSansSC-Bold.ttf" in FONT_FILES
