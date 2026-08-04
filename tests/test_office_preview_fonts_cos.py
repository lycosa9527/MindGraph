"""Unit tests for Showcase office-preview font COS helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.infrastructure.sync.cos_sync_env import (
    office_preview_font_cos_key,
    office_preview_fonts_meta_cos_key,
    office_preview_fonts_rel_prefix,
)
from services.infrastructure.sync.office_preview_fonts_cos import (
    FONT_FILES,
    is_allowed_office_preview_font,
    write_office_preview_fontconfig,
)


def test_font_allowlist() -> None:
    """Common Windows CJK basenames only."""
    assert is_allowed_office_preview_font("simsun.ttc")
    assert is_allowed_office_preview_font("simkai.ttf")
    assert is_allowed_office_preview_font("msyh.ttc")
    assert not is_allowed_office_preview_font("evil.ttf")
    assert not is_allowed_office_preview_font("../simsun.ttc")


def test_cos_keys_under_sync_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """COS keys stay under sync/fonts/office-preview."""
    monkeypatch.setenv("COS_SYNC_KEY_PREFIX", "backups/mindgraph-shared")
    assert office_preview_fonts_rel_prefix() == "sync/fonts/office-preview"
    assert office_preview_font_cos_key("simsun.ttc") == (
        "backups/mindgraph-shared/sync/fonts/office-preview/simsun.ttc"
    )
    assert office_preview_fonts_meta_cos_key().endswith("/sync/fonts/office-preview/meta.json")


def test_cos_key_rejects_path_traversal() -> None:
    """Path segments must not escape the COS prefix."""
    with pytest.raises(ValueError):
        office_preview_font_cos_key("../secret.ttf")


def test_font_files_include_song_kai_fang() -> None:
    """Pack covers 宋体/黑体/楷体/仿宋/微软雅黑."""
    assert "simsun.ttc" in FONT_FILES
    assert "simhei.ttf" in FONT_FILES
    assert "simkai.ttf" in FONT_FILES
    assert "simfang.ttf" in FONT_FILES
    assert "msyh.ttc" in FONT_FILES


def test_write_fontconfig_includes_dir_and_aliases(tmp_path: Path) -> None:
    """Generated fonts.conf points at the cache dir and Chinese aliases."""
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    conf = write_office_preview_fontconfig(tmp_path / "fonts.conf", fonts_dir)
    text = conf.read_text(encoding="utf-8")
    assert str(fonts_dir.resolve()) in text
    assert "宋体" in text
    assert "楷体" in text
    assert "SimSun" in text
