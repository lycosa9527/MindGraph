"""Search indexing: robots.txt, sitemap, and crawlable brand text."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from services.infrastructure.utils.search_indexing import (
    SEARCH_DESCRIPTION,
    build_robots_txt,
    build_sitemap_xml,
    robots_allows,
)
from utils.privacy_policy_static import build_privacy_policy_html

vue_spa_module = importlib.import_module("routers.core.vue_spa")

_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/auth", True),
        ("/privacy", True),
        ("/sitemap.xml", True),
        ("/", False),
        ("/canvas", False),
        ("/mindgraph", False),
        ("/admin", False),
        ("/privacy/extension", False),
        ("/privacy-policy.html", False),
        ("/login", False),
    ],
)
def test_robots_allows_public_pages_only(path: str, allowed: bool) -> None:
    """Signed-out public pages are crawlable; the app is not."""
    robots = build_robots_txt("https://mg.example.com")
    assert robots_allows(robots, path) is allowed


def test_robots_and_sitemap_use_request_origin() -> None:
    """Sitemap locations and the robots Sitemap line follow the public host."""
    origin = "https://mg.example.com"
    robots = build_robots_txt(origin)
    sitemap = build_sitemap_xml(origin)
    assert "Sitemap: https://mg.example.com/sitemap.xml" in robots
    assert "<loc>https://mg.example.com/auth</loc>" in sitemap
    assert "<loc>https://mg.example.com/privacy</loc>" in sitemap
    assert "/canvas" not in sitemap


def test_public_shell_and_privacy_name_the_product() -> None:
    """The first HTML response names MindGraph and Mind Platform for non-JS crawlers."""
    index_html = (_REPO_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    static_robots = (_REPO_ROOT / "frontend" / "public" / "robots.txt").read_text(encoding="utf-8")
    privacy_html = build_privacy_policy_html()
    assert SEARCH_DESCRIPTION in index_html
    assert "<title>MindGraph · Mind Platform</title>" in index_html
    assert "MindGraph" in privacy_html
    assert "Mind Platform" in privacy_html
    assert "迈特教研" in privacy_html
    assert SEARCH_DESCRIPTION in privacy_html
    assert robots_allows(static_robots, "/auth") is True
    assert robots_allows(static_robots, "/canvas") is False


def test_search_routes_follow_host_header(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /robots.txt and /sitemap.xml use the Host the crawler requested."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!doctype html><html><head><title>Mind Platform</title></head><body></body></html>",
        encoding="utf-8",
    )
    monkeypatch.setattr(vue_spa_module, "VUE_DIST_DIR", dist)
    app = FastAPI()
    app.include_router(vue_spa_module.router)
    client = TestClient(app)
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("EXTERNAL_BASE_URL", None)
        robots = client.get("/robots.txt", headers={"host": "mg.example.com"})
        sitemap = client.get("/sitemap.xml", headers={"host": "mg.example.com"})
        auth = client.get("/auth", headers={"host": "mg.example.com"})
        canvas = client.get("/canvas", headers={"host": "mg.example.com"})
    assert robots.status_code == 200
    assert robots.headers["content-type"].startswith("text/plain")
    assert "Sitemap: http://mg.example.com/sitemap.xml" in robots.text
    assert robots_allows(robots.text, "/auth") is True
    assert robots_allows(robots.text, "/mindgraph") is False
    assert sitemap.status_code == 200
    assert sitemap.headers["content-type"].startswith("application/xml")
    assert "<loc>http://mg.example.com/auth</loc>" in sitemap.text
    assert "<title>MindGraph · Mind Platform</title>" in auth.text
    assert SEARCH_DESCRIPTION in auth.text
    assert "<noscript>" in auth.text
    assert 'rel="canonical" href="http://mg.example.com/auth"' in auth.text
    assert 'name="robots"' not in auth.text
    assert 'name="robots" content="noindex, nofollow"' in canvas.text
