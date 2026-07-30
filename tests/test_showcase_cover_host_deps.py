"""Unit tests for Showcase LibreOffice / CJK font startup gates."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.showcase.covers import host_deps


def test_lines_showcase_cover_host_install_has_apt_and_verify() -> None:
    """Install hints include apt packages and verification commands."""
    text = "\n".join(host_deps.lines_showcase_cover_host_install())
    assert "sudo apt-get install -y" in text
    assert "libreoffice-writer" in text
    assert "libreoffice-impress" in text
    assert "fonts-noto-cjk" in text
    assert "soffice --version" in text
    assert "loimpress" in text
    assert "lowriter" in text
    assert "fc-list :lang=zh" in text
    assert "SHOWCASE_SERVER_COVERS=false" in text


def test_check_libreoffice_installed_ok() -> None:
    """Accept soffice when --version returns a banner and Writer+Impress are present."""
    with (
        patch.object(host_deps, "resolve_soffice_path", return_value="/usr/bin/soffice"),
        patch.object(host_deps, "writer_component_installed", return_value=True),
        patch.object(host_deps, "impress_component_installed", return_value=True),
        patch.object(host_deps.subprocess, "run") as run_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stdout="LibreOffice 24.2.0\n", stderr="")
        ok, message = host_deps.check_libreoffice_installed()
    assert ok is True
    assert "LibreOffice 24.2.0" in message
    assert "Writer" in message
    assert "Impress" in message
    assert "/usr/bin/soffice" in message


def test_check_libreoffice_installed_missing() -> None:
    """Fail with apt install hint when soffice cannot be resolved."""
    with patch.object(host_deps, "resolve_soffice_path", return_value=None):
        ok, message = host_deps.check_libreoffice_installed()
    assert ok is False
    assert "not found" in message.lower()
    assert "sudo apt-get install -y" in message
    assert "libreoffice-writer" in message
    assert "libreoffice-impress" in message


def test_check_libreoffice_installed_missing_impress() -> None:
    """Fail when soffice exists but Impress is not installed (writer-only)."""
    with (
        patch.object(host_deps, "resolve_soffice_path", return_value="/usr/bin/soffice"),
        patch.object(host_deps, "writer_component_installed", return_value=True),
        patch.object(host_deps, "impress_component_installed", return_value=False),
        patch.object(host_deps.subprocess, "run") as run_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stdout="LibreOffice 24.2.0\n", stderr="")
        ok, message = host_deps.check_libreoffice_installed()
    assert ok is False
    assert "impress" in message.lower()
    assert "sudo apt-get install -y" in message
    assert "libreoffice-impress" in message


def test_check_libreoffice_installed_missing_writer() -> None:
    """Fail when soffice exists but Writer is not installed (impress-only)."""
    with (
        patch.object(host_deps, "resolve_soffice_path", return_value="/usr/bin/soffice"),
        patch.object(host_deps, "writer_component_installed", return_value=False),
        patch.object(host_deps, "impress_component_installed", return_value=True),
        patch.object(host_deps.subprocess, "run") as run_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stdout="LibreOffice 24.2.0\n", stderr="")
        ok, message = host_deps.check_libreoffice_installed()
    assert ok is False
    assert "writer" in message.lower()
    assert "sudo apt-get install -y" in message
    assert "libreoffice-writer" in message


def test_impress_component_installed_via_loimpress_which() -> None:
    """Accept Impress when loimpress is on PATH."""

    def which_loimpress(name: str) -> str | None:
        return "/usr/bin/loimpress" if name == "loimpress" else None

    with patch.object(host_deps.shutil, "which", side_effect=which_loimpress):
        assert host_deps.impress_component_installed("/usr/bin/soffice") is True


def test_writer_component_installed_via_program_swriter(tmp_path) -> None:
    """Accept Writer when program/swriter exists next to soffice."""
    program = tmp_path / "program"
    program.mkdir()
    (program / "soffice").write_text("", encoding="utf-8")
    (program / "swriter").write_text("", encoding="utf-8")
    with patch.object(host_deps.shutil, "which", return_value=None):
        assert host_deps.writer_component_installed(str(program / "soffice")) is True


def test_impress_component_installed_via_program_simpress(tmp_path) -> None:
    """Accept Impress when program/simpress exists next to soffice."""
    program = tmp_path / "program"
    program.mkdir()
    (program / "soffice").write_text("", encoding="utf-8")
    (program / "simpress").write_text("", encoding="utf-8")
    with patch.object(host_deps.shutil, "which", return_value=None):
        assert host_deps.impress_component_installed(str(program / "soffice")) is True


def test_check_noto_cjk_fonts_linux_ok() -> None:
    """Pass when fc-list reports a Noto CJK family."""
    with (
        patch.object(host_deps.sys, "platform", "linux"),
        patch.object(host_deps.shutil, "which", return_value="/usr/bin/fc-list"),
        patch.object(host_deps, "_fc_list_output", return_value="Noto Sans CJK SC\n"),
    ):
        ok, message = host_deps.check_noto_cjk_fonts_installed()
    assert ok is True
    assert "Noto" in message


def test_check_noto_cjk_fonts_linux_missing_package() -> None:
    """Fail with apt + fc-list verify when Noto/Source Han is absent."""
    with (
        patch.object(host_deps.sys, "platform", "linux"),
        patch.object(host_deps.shutil, "which", return_value="/usr/bin/fc-list"),
        patch.object(host_deps, "_fc_list_output", return_value="WenQuanYi Micro Hei\n"),
    ):
        ok, message = host_deps.check_noto_cjk_fonts_installed()
    assert ok is False
    assert "fonts-noto-cjk" in message
    assert "fc-list :lang=zh" in message


def test_enforce_exits_when_covers_enabled_and_deps_missing() -> None:
    """Hard-fail boot when Showcase covers are on and LibreOffice is missing."""
    with (
        patch.object(host_deps, "showcase_server_covers_enabled", return_value=True),
        patch.object(host_deps, "check_libreoffice_installed", return_value=(False, "missing")),
        patch.object(host_deps, "check_noto_cjk_fonts_installed", return_value=(True, "ok")),
        pytest.raises(SystemExit) as exited,
    ):
        host_deps.enforce_showcase_cover_host_deps_or_exit()
    assert exited.value.code == 1


def test_enforce_skips_when_covers_disabled() -> None:
    """Do not probe host deps when server covers are disabled."""
    with (
        patch.object(host_deps, "showcase_server_covers_enabled", return_value=False),
        patch.object(host_deps, "check_libreoffice_installed") as lo_check,
    ):
        host_deps.enforce_showcase_cover_host_deps_or_exit()
    lo_check.assert_not_called()
