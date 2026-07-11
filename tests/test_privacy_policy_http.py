"""HTTP and static-file tests for Google-crawlable privacy policy."""

from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from scripts.check_privacy_policy_crawlable import is_google_crawlable_privacy_html
from utils.privacy_policy_static import build_privacy_policy_html, write_privacy_policy_files

vue_spa_module = importlib.import_module("routers.core.vue_spa")


def _privacy_test_app() -> FastAPI:
    """Minimal app mounting the Vue SPA router (matches test_spa_cache_control)."""
    app = FastAPI()
    app.include_router(vue_spa_module.router)
    return app


def test_privacy_static_file_is_google_crawlable() -> None:
    """On-disk privacy-policy.html must not depend on JavaScript."""
    paths = write_privacy_policy_files()
    html = paths[0].read_text(encoding="utf-8")
    ok, issues = is_google_crawlable_privacy_html(html)
    assert ok, issues


def test_privacy_route_serves_static_html(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /privacy returns static HTML, not the Vue SPA shell."""
    public = tmp_path / "frontend" / "public"
    public.mkdir(parents=True)
    policy_path = public / "privacy-policy.html"
    policy_path.write_text(
        ('<!DOCTYPE html><html><body><section id="browser-extension">Extension privacy</section></body></html>'),
        encoding="utf-8",
    )
    monkeypatch.setattr(vue_spa_module, "VUE_DIST_DIR", tmp_path / "dist")
    monkeypatch.setattr(
        "utils.privacy_policy_static._PRIVACY_HTML_PATHS",
        (policy_path, tmp_path / "static" / "privacy-policy.html"),
    )

    client = TestClient(_privacy_test_app())
    response = client.get("/privacy")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'id="browser-extension"' in response.text
    assert "Mind Platform" not in response.text
    assert "/assets/index-" not in response.text


def test_privacy_policy_html_dist_path_is_google_crawlable(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /privacy-policy.html serves the static file from dist without SPA fallback."""
    dist = tmp_path / "dist"
    dist.mkdir()
    policy = dist / "privacy-policy.html"
    policy.write_text(build_privacy_policy_html(), encoding="utf-8")
    monkeypatch.setattr(vue_spa_module, "VUE_DIST_DIR", dist)

    client = TestClient(_privacy_test_app())
    response = client.get("/privacy-policy.html")
    assert response.status_code == 200
    ok, issues = is_google_crawlable_privacy_html(response.text)
    assert ok, issues
