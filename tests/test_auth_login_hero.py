"""Public /auth login-hero COS 302 and local fallback."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from starlette.testclient import TestClient

from config.settings import config
from routers.auth import login_hero as login_hero_routes
from scripts.auth_login_video.publish import hero_cos_prefixes
from services.auth import login_hero_media


def _hero_app() -> FastAPI:
    app = FastAPI()
    app.include_router(login_hero_routes.router, prefix="/api/auth")
    return app


def test_unknown_login_hero_is_404() -> None:
    """Unknown clip ids must not leak a listing."""
    client = TestClient(_hero_app())
    response = client.get("/api/auth/login-hero/99-missing.mp4")
    assert response.status_code == 404


def test_local_login_hero_file(tmp_path, monkeypatch) -> None:
    """When COS is off, serve the silent desktop reencode."""
    clip = tmp_path / "02-mind-leap-reencode.mp4"
    clip.write_bytes(b"0" * 20000)
    monkeypatch.setattr(login_hero_media, "DESKTOP_DIR", tmp_path)
    monkeypatch.setattr(login_hero_routes, "hero_presigned_url", lambda _clip_id: None)
    client = TestClient(_hero_app())
    response = client.get("/api/auth/login-hero/02-mind-leap.mp4")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert len(response.content) == 20000


def test_cos_login_hero_redirects(monkeypatch) -> None:
    """Browser follows a 302 to the private-bucket presign."""
    monkeypatch.setattr(
        login_hero_routes,
        "hero_presigned_url",
        lambda _clip_id: "https://example.com/01-awaken-cosmos.mp4",
    )
    client = TestClient(_hero_app())
    response = client.get("/api/auth/login-hero/01-awaken-cosmos.mp4", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/01-awaken-cosmos.mp4"


def test_vite_dev_port_skips_cos_presign(monkeypatch) -> None:
    """Vite local cannot fetch COS, so /auth must not 302 there."""
    monkeypatch.setenv("VITE_DEV_PORT", "5173")
    monkeypatch.setenv("DEBUG", "true")
    assert login_hero_media.hero_presigned_url("01-awaken-cosmos") is None


def test_debug_host_still_presigns_cos(monkeypatch) -> None:
    """Test server may keep DEBUG=true and still 302 to COS."""
    monkeypatch.delenv("VITE_DEV_PORT", raising=False)
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setattr(
        login_hero_media,
        "config",
        SimpleNamespace(
            COS_AUTH_LOGIN_ENABLED=True,
            COS_AUTH_LOGIN_PREFIX="test/auth-login",
            COS_AUTH_LOGIN_PRESIGN_GET_TTL=3600,
        ),
    )
    monkeypatch.setattr(login_hero_media, "cos_credentials_configured", lambda: True)
    monkeypatch.setattr(
        login_hero_media,
        "generate_presigned_get_url",
        lambda *_args, **_kwargs: "https://example.com/hero.mp4",
    )
    assert login_hero_media.hero_presigned_url("01-awaken-cosmos") == ("https://example.com/hero.mp4")


def test_hero_cos_prefixes_cover_shared_and_live(monkeypatch) -> None:
    """One publish writes dev, test, and live production keys."""
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)
    monkeypatch.delenv("COS_AUTH_LOGIN_PREFIX", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    config.refresh_env_cache()
    try:
        prefixes = hero_cos_prefixes()
        assert "dev/auth-login" in prefixes
        assert "test/auth-login" in prefixes
        assert "auth-login/mindgraph" in prefixes
    finally:
        config.refresh_env_cache()
