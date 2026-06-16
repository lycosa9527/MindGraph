"""Vue SPA static file MIME types and /index.html serving tests."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.infrastructure.utils.spa_handler import media_type_for_vue_dist_relpath

vue_spa_module = importlib.import_module("routers.core.vue_spa")


@pytest.mark.parametrize(
    ("relpath", "expected"),
    [
        ("index.html", "text/html"),
        ("subdir/page.HTML", "text/html"),
        ("sw.js", "text/javascript"),
        ("workbox-abc.mjs", "text/javascript"),
        ("manifest.webmanifest", "application/manifest+json"),
        ("robots.txt", "text/plain"),
        ("pwa-192x192.png", "image/png"),
        ("favicon.svg", "image/svg+xml"),
        ("font.woff2", "font/woff2"),
        ("unknown.bin", "application/octet-stream"),
    ],
)
def test_media_type_for_vue_dist_relpath(relpath: str, expected: str) -> None:
    assert media_type_for_vue_dist_relpath(relpath) == expected


def test_index_html_route_serves_text_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    index_path = dist_dir / "index.html"
    index_path.write_text("<!doctype html><html><body>ok</body></html>", encoding="utf-8")

    monkeypatch.setattr(vue_spa_module, "VUE_DIST_DIR", dist_dir)

    app = FastAPI()
    app.include_router(vue_spa_module.router)
    client = TestClient(app)

    for path in ("/index.html", "/"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "ok" in response.text


def test_catch_all_index_html_serves_text_html(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch-all static branch must not treat index.html as octet-stream (PWA SW fallback)."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    nested = dist_dir / "nested"
    nested.mkdir()
    html_path = nested / "offline.html"
    html_path.write_text("<!doctype html><html><body>offline</body></html>", encoding="utf-8")

    monkeypatch.setattr(vue_spa_module, "VUE_DIST_DIR", dist_dir)

    app = FastAPI()
    app.include_router(vue_spa_module.router)
    client = TestClient(app)

    response = client.get("/nested/offline.html")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "offline" in response.text
