"""Unit tests for Showcase LibreOffice high-quality PDF export filter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.showcase.covers.office_to_pdf import (
    build_office_pdf_convert_to,
    convert_office_to_pdf,
    office_suffix_needs_pdf,
)


def test_office_suffix_needs_pdf() -> None:
    """Only Office teaching-doc suffixes go through LibreOffice."""
    assert office_suffix_needs_pdf(".docx")
    assert office_suffix_needs_pdf(".DOC")
    assert office_suffix_needs_pdf(".pptx")
    assert not office_suffix_needs_pdf(".pdf")


def test_build_office_pdf_convert_to_docx() -> None:
    """Writer filter with lossless / no-downsample options (compact JSON)."""
    token = build_office_pdf_convert_to(".docx")
    assert token.startswith("pdf:writer_pdf_Export:")
    assert " " not in token
    options = json.loads(token.split(":", maxsplit=2)[2])
    assert options["UseLosslessCompression"] == {"type": "boolean", "value": "true"}
    assert options["Quality"] == {"type": "long", "value": "100"}
    assert options["ReduceImageResolution"] == {"type": "boolean", "value": "false"}


def test_build_office_pdf_convert_to_doc_matches_docx() -> None:
    """Legacy .doc uses the same Writer PDF export filter as .docx."""
    assert build_office_pdf_convert_to(".doc") == build_office_pdf_convert_to(".docx")


def test_build_office_pdf_convert_to_pptx() -> None:
    """Impress filter for PPTX."""
    token = build_office_pdf_convert_to(".pptx")
    assert token.startswith("pdf:impress_pdf_Export:")
    options = json.loads(token.split(":", maxsplit=2)[2])
    assert options["UseLosslessCompression"]["value"] == "true"


def test_build_office_pdf_convert_to_rejects_pdf() -> None:
    """Native PDF must not go through Office export filters."""
    with pytest.raises(ValueError, match="Unsupported"):
        build_office_pdf_convert_to(".pdf")


def test_convert_office_to_pdf_passes_filter_token(tmp_path: Path) -> None:
    """convert_office_to_pdf must pass the high-quality --convert-to token."""
    source = tmp_path / "lesson.docx"
    source.write_bytes(b"PK fake")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    produced = out_dir / "lesson.pdf"
    produced.write_bytes(b"%PDF-1.7")

    completed = MagicMock()
    completed.returncode = 0
    completed.stderr = ""
    completed.stdout = ""

    with (
        patch(
            "services.showcase.covers.office_to_pdf.resolve_soffice_path",
            return_value="/usr/bin/soffice",
        ),
        patch(
            "services.showcase.covers.office_to_pdf.ensure_office_preview_fonts_ready",
            return_value={},
        ),
        patch(
            "services.showcase.covers.office_to_pdf.office_preview_fontconfig_env",
            return_value={"FONTCONFIG_FILE": "/tmp/fonts.conf", "PATH": "/usr/bin"},
        ),
        patch(
            "services.showcase.covers.office_to_pdf.subprocess.run",
            return_value=completed,
        ) as run_mock,
    ):
        result = convert_office_to_pdf(source, out_dir)

    assert result == produced
    cmd = run_mock.call_args.args[0]
    assert "--convert-to" in cmd
    convert_arg = cmd[cmd.index("--convert-to") + 1]
    assert convert_arg == build_office_pdf_convert_to(".docx")
    assert run_mock.call_args.kwargs["env"]["FONTCONFIG_FILE"] == "/tmp/fonts.conf"
