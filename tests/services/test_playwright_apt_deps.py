"""Tests for Playwright apt-deps helpers."""

from __future__ import annotations

from pathlib import Path

from services.infrastructure.sync import playwright_apt_deps


def test_playwright_required_apt_packages_ubuntu24(monkeypatch):
    monkeypatch.setattr(
        playwright_apt_deps,
        "playwright_apt_distro_key",
        lambda: "ubuntu24.04-x64",
    )
    packages = playwright_apt_deps.playwright_required_apt_packages("ubuntu24.04-x64")
    assert "xvfb" in packages
    assert "fonts-wqy-zenhei" in packages
    assert "libasound2t64" in packages
    assert "libnss3" in packages
    # firefox/webkit-only packages should not be included
    assert "libavcodec60" not in packages


def test_local_deb_install_args_prefix_dot_slash():
    files = [
        Path("/tmp/debs/xvfb_2%3a21.1.12_amd64.deb"),
        Path("/tmp/debs/libnss3_2_amd64.deb"),
    ]
    assert playwright_apt_deps.local_deb_install_args(files) == [
        "./xvfb_2%3a21.1.12_amd64.deb",
        "./libnss3_2_amd64.deb",
    ]


def test_playwright_apt_distro_key_ubuntu(monkeypatch):
    monkeypatch.setattr(playwright_apt_deps.platform, "system", lambda: "Linux")
    monkeypatch.setattr(playwright_apt_deps.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        playwright_apt_deps,
        "linux_os_release",
        lambda: {"ID": "ubuntu", "VERSION_ID": "24.04"},
    )
    assert playwright_apt_deps.playwright_apt_distro_key() == "ubuntu24.04-x64"
