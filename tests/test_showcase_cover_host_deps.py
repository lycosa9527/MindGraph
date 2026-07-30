"""Unit tests for Showcase LibreOffice / CJK font startup gates."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.showcase.covers import host_deps


def test_check_libreoffice_installed_ok() -> None:
    """Accept soffice when --version returns a banner."""
    with (
        patch.object(host_deps, "resolve_soffice_path", return_value="/usr/bin/soffice"),
        patch.object(host_deps.subprocess, "run") as run_mock,
    ):
        run_mock.return_value = MagicMock(returncode=0, stdout="LibreOffice 24.2.0\n", stderr="")
        ok, message = host_deps.check_libreoffice_installed()
    assert ok is True
    assert "LibreOffice 24.2.0" in message
    assert "/usr/bin/soffice" in message


def test_check_libreoffice_installed_missing() -> None:
    """Fail clearly when soffice cannot be resolved."""
    with patch.object(host_deps, "resolve_soffice_path", return_value=None):
        ok, message = host_deps.check_libreoffice_installed()
    assert ok is False
    assert "not found" in message.lower()


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
    """Fail when Chinese fonts exist but Noto/Source Han is absent."""
    with (
        patch.object(host_deps.sys, "platform", "linux"),
        patch.object(host_deps.shutil, "which", return_value="/usr/bin/fc-list"),
        patch.object(host_deps, "_fc_list_output", return_value="WenQuanYi Micro Hei\n"),
    ):
        ok, message = host_deps.check_noto_cjk_fonts_installed()
    assert ok is False
    assert "fonts-noto-cjk" in message


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
