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
    google_site_verification_token,
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
        ("/", True),
        ("/auth/", False),
        ("/authentication", False),
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
    assert "Allow: /$" in robots
    assert "<loc>https://mg.example.com/</loc>" in sitemap
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
    assert robots_allows(static_robots, "/") is True
    assert robots_allows(static_robots, "/auth") is True
    assert robots_allows(static_robots, "/canvas") is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Abcdefghij1234_-", "Abcdefghij1234_-"),
        ("  Abcdefghij1234  ", "Abcdefghij1234"),
        ("", ""),
        ("short", ""),
        ("has space tokenvalue", ""),
        ("<script>alert(1)</script>", ""),
    ],
)
def test_google_site_verification_token_is_a_plain_code(raw: str, expected: str) -> None:
    """Search Console tokens are a single code. Markup and blanks are ignored."""
    assert google_site_verification_token(raw) == expected


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
        os.environ.pop("GOOGLE_SITE_VERIFICATION", None)
        robots = client.get("/robots.txt", headers={"host": "mg.example.com"})
        sitemap = client.get("/sitemap.xml", headers={"host": "mg.example.com"})
        home = client.get("/", headers={"host": "mg.example.com"})
        auth = client.get("/auth", headers={"host": "mg.example.com"})
        auth_slash = client.get("/auth/", headers={"host": "mg.example.com"})
        canvas = client.get("/canvas", headers={"host": "mg.example.com"})
    assert robots.status_code == 200
    assert robots.headers["content-type"].startswith("text/plain")
    assert "Sitemap: https://mg.example.com/sitemap.xml" in robots.text
    assert robots_allows(robots.text, "/") is True
    assert robots_allows(robots.text, "/auth") is True
    assert robots_allows(robots.text, "/mindgraph") is False
    assert sitemap.status_code == 200
    assert sitemap.headers["content-type"].startswith("application/xml")
    assert "<loc>https://mg.example.com/</loc>" in sitemap.text
    assert "<loc>https://mg.example.com/auth</loc>" in sitemap.text
    assert "<title>MindGraph · Mind Platform</title>" in home.text
    assert SEARCH_DESCRIPTION in home.text
    assert 'rel="canonical" href="https://mg.example.com/"' in home.text
    assert "google-site-verification" not in home.text
    assert 'name="robots"' not in home.text
    assert "<title>MindGraph · Mind Platform</title>" in auth.text
    assert SEARCH_DESCRIPTION in auth.text
    assert "<noscript>" in auth.text
    assert 'rel="canonical" href="https://mg.example.com/auth"' in auth.text
    assert 'name="robots"' not in auth.text
    assert 'name="robots" content="noindex, nofollow"' in auth_slash.text
    assert 'name="robots" content="noindex, nofollow"' in canvas.text


def test_google_site_verification_is_only_on_public_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Search Console tag is on the three public pages and nowhere else."""
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
    token = "Abcdefghij1234_-"
    with patch.dict(os.environ, {"GOOGLE_SITE_VERIFICATION": token}, clear=False):
        os.environ.pop("EXTERNAL_BASE_URL", None)
        home = client.get("/", headers={"host": "mg.example.com"})
        auth = client.get("/auth", headers={"host": "mg.example.com"})
        privacy = client.get("/privacy", headers={"host": "mg.example.com"})
        canvas = client.get("/canvas", headers={"host": "mg.example.com"})
    tag = f'<meta name="google-site-verification" content="{token}" />'
    assert tag in home.text
    assert tag in auth.text
    assert tag in privacy.text
    assert "google-site-verification" not in canvas.text
