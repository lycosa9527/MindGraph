"""Tests for LibreOffice legacy Office conversion helper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.knowledge.legacy_office_convert import (
    convert_legacy_office,
    is_legacy_office_mime,
    resolve_soffice_path,
)


def test_is_legacy_office_mime() -> None:
    """Only classic OLE Office MIME types are treated as legacy."""
    assert is_legacy_office_mime("application/msword") is True
    assert is_legacy_office_mime("application/vnd.ms-powerpoint") is True
    assert is_legacy_office_mime("application/vnd.ms-excel") is True
    assert is_legacy_office_mime("application/vnd.openxmlformats-officedocument.wordprocessingml.document") is False


def test_convert_legacy_office_requires_soffice(tmp_path: Path) -> None:
    """Missing LibreOffice yields a clear ValueError."""
    source = tmp_path / "notes.doc"
    source.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32)
    with patch("services.knowledge.legacy_office_convert.resolve_soffice_path", return_value=None):
        with pytest.raises(ValueError, match="LibreOffice"):
            convert_legacy_office(str(source), "application/msword", str(tmp_path / "out"))


def test_convert_legacy_office_success(tmp_path: Path) -> None:
    """Successful soffice run returns the converted OOXML path and MIME."""
    source = tmp_path / "deck.ppt"
    source.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    converted = out_dir / "deck.pptx"
    converted.write_bytes(b"PK\x03\x04fake")

    completed = MagicMock(returncode=0, stderr="", stdout="")
    with (
        patch("services.knowledge.legacy_office_convert.resolve_soffice_path", return_value="/usr/bin/soffice"),
        patch("services.knowledge.legacy_office_convert.subprocess.run", return_value=completed) as run_mock,
    ):
        path, mime = convert_legacy_office(
            str(source),
            "application/vnd.ms-powerpoint",
            str(out_dir),
        )

    assert path == str(converted)
    assert mime.endswith("presentationml.presentation")
    assert run_mock.called


def test_resolve_soffice_path_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """LIBREOFFICE_PATH env points at an explicit binary."""
    binary = tmp_path / "soffice"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("LIBREOFFICE_PATH", str(binary))
    assert resolve_soffice_path() == str(binary)
