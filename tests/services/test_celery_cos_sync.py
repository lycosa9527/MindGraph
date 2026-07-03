"""Tests for Celery COS sync."""

from __future__ import annotations

import zipfile
from pathlib import Path

from services.infrastructure.sync import celery_cos_sync, celery_release


def test_parse_celery_wheel_version():
    assert celery_release.parse_celery_wheel_version(Path("celery-5.6.3-py3-none-any.whl")) == "5.6.3"


def test_resolve_celery_wheel_path_whls(tmp_path):
    wheel = tmp_path / "celery-5.6.3-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    assert celery_release.resolve_celery_wheel_path(wheel) == wheel


def test_resolve_celery_wheel_path_zip_without_wheel(tmp_path):
    archive = tmp_path / "celery-5.6.3.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("celery-5.6.3/README.rst", "source only")
    assert celery_release.resolve_celery_wheel_path(archive) is None


def test_celery_cos_update_needed_cos_newer(monkeypatch):
    monkeypatch.setattr(
        celery_cos_sync,
        "read_celery_cos_meta",
        lambda: {"version": "5.6.3", "wheel_filename": "celery-5.6.3-py3-none-any.whl"},
    )
    monkeypatch.setattr(
        celery_cos_sync,
        "detect_installed_celery_version",
        lambda: "5.6.2",
    )
    plan = celery_cos_sync.celery_cos_update_needed()
    assert plan["update_needed"] is True
    assert plan["reason"] == "cos_newer"
    assert plan["cos_version"] == "5.6.3"


def test_celery_cos_update_needed_up_to_date(monkeypatch):
    monkeypatch.setattr(
        celery_cos_sync,
        "read_celery_cos_meta",
        lambda: {"version": "5.6.3"},
    )
    monkeypatch.setattr(
        celery_cos_sync,
        "detect_installed_celery_version",
        lambda: "5.6.3",
    )
    plan = celery_cos_sync.celery_cos_update_needed()
    assert plan["update_needed"] is False
    assert plan["reason"] == "up_to_date"


def test_celery_cos_update_needed_not_installed(monkeypatch):
    monkeypatch.setattr(
        celery_cos_sync,
        "read_celery_cos_meta",
        lambda: {"version": "5.6.3"},
    )
    monkeypatch.setattr(
        celery_cos_sync,
        "detect_installed_celery_version",
        lambda: None,
    )
    plan = celery_cos_sync.celery_cos_update_needed()
    assert plan["update_needed"] is True
    assert plan["reason"] == "not_installed"
