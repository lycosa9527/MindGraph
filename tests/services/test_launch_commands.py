"""Tests for launch_commands helpers."""

from __future__ import annotations

from services.infrastructure.utils.launch_commands import (
    lines_fail2ban_host_install,
    lines_optional_feature_packages,
    lines_playwright_hint,
    lines_tesseract_hint,
    redis_port_from_url,
)


def test_redis_port_from_url_default() -> None:
    assert redis_port_from_url("redis://localhost:6379/0") == 6379


def test_redis_port_from_url_custom() -> None:
    assert redis_port_from_url("redis://127.0.0.1:6380/1") == 6380


def test_tesseract_hint_includes_pip() -> None:
    text = "\n".join(lines_tesseract_hint())
    assert "pytesseract" in text
    assert "playwright" not in text.lower()


def test_playwright_hint_includes_install_chromium() -> None:
    text = "\n".join(lines_playwright_hint())
    assert "playwright install chromium" in text


def test_optional_feature_packages_covers_geo_and_extras() -> None:
    text = "\n".join(lines_optional_feature_packages())
    assert "py-ip2region" in text
    assert "cos-python-sdk-v5" in text
    assert "GeoLite2-Country" in text
    assert "run_migrations" in text
    assert "dashboard_install" in text
    assert "build_prompt_language_registry" in text


def test_fail2ban_host_install_lists_apt() -> None:
    text = "\n".join(lines_fail2ban_host_install())
    assert "apt install fail2ban" in text
