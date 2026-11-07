"""GET /api/proxy-image reads this host's temp PNGs without a public fetch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse

from routers.api import image_proxy
from routers.api import png_export as png_mod

_PNG_NAME = "dingtalk_deadbeef_1710000000.png"
_WWW = "https://www.mindspringedu.com"


@pytest.mark.asyncio
async def test_proxy_image_reads_local_temp_png(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A www temp-image URL on this server is the file on disk, not an HTTP hop."""
    monkeypatch.setenv("EXTERNAL_BASE_URL", _WWW)
    local = tmp_path / _PNG_NAME
    local.write_bytes(b"\x89PNG\r\n")
    url = f"https://mg.mindspringedu.com/api/temp_images/{_PNG_NAME}"
    with (
        patch.object(png_mod, "TEMP_IMAGES_DIR", tmp_path),
        patch.object(image_proxy.httpx, "AsyncClient") as client,
    ):
        response = await image_proxy.proxy_image(url)
    client.assert_not_called()
    assert isinstance(response, FileResponse)
    assert response.path == str(local)


@pytest.mark.asyncio
async def test_missing_local_temp_png_does_not_fetch_public_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing file on this host is 404. The proxy must not call itself via DNS."""
    monkeypatch.setenv("EXTERNAL_BASE_URL", _WWW)
    url = f"{_WWW}/api/temp_images/{_PNG_NAME}"
    with (
        patch.object(png_mod, "TEMP_IMAGES_DIR", tmp_path),
        patch.object(image_proxy.httpx, "AsyncClient") as client,
        pytest.raises(HTTPException) as exc_info,
    ):
        await image_proxy.proxy_image(url)
    assert exc_info.value.status_code == 404
    client.assert_not_called()


@pytest.mark.asyncio
async def test_same_host_non_temp_image_stays_on_https(monkeypatch: pytest.MonkeyPatch) -> None:
    """Files this process does not store stay on the public URL. Nginx serves those."""
    monkeypatch.setenv("EXTERNAL_BASE_URL", _WWW)
    fake = MagicMock()
    fake.status_code = 200
    fake.headers = {"content-type": "image/png"}
    fake.content = b"\x89PNG"
    client = AsyncMock()
    client.get = AsyncMock(return_value=fake)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    url = f"{_WWW}/assets/logo.png"
    with patch.object(image_proxy.httpx, "AsyncClient", return_value=client):
        response = await image_proxy.proxy_image(url)
    client.get.assert_awaited_once_with(url, follow_redirects=False)
    assert response.body == b"\x89PNG"


@pytest.mark.asyncio
async def test_other_mindgraph_host_stays_on_https(monkeypatch: pytest.MonkeyPatch) -> None:
    """A temp image on www is fetched over HTTPS when this process is another host."""
    monkeypatch.setenv("EXTERNAL_BASE_URL", "https://test.example.com")
    fake = MagicMock()
    fake.status_code = 200
    fake.headers = {"content-type": "image/png"}
    fake.content = b"\x89PNG"
    client = AsyncMock()
    client.get = AsyncMock(return_value=fake)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    url = f"{_WWW}/api/temp_images/{_PNG_NAME}"
    with patch.object(image_proxy.httpx, "AsyncClient", return_value=client):
        await image_proxy.proxy_image(url)
    called_url = client.get.await_args.args[0]
    assert called_url == url


@pytest.mark.asyncio
async def test_proxy_image_timeout_is_504(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hung upstream image is a gateway timeout."""
    monkeypatch.setenv("EXTERNAL_BASE_URL", "https://test.example.com")
    client = AsyncMock()
    client.get = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    url = f"{_WWW}/assets/logo.png"
    with (
        patch.object(image_proxy.httpx, "AsyncClient", return_value=client),
        pytest.raises(HTTPException) as exc_info,
    ):
        await image_proxy.proxy_image(url)
    assert exc_info.value.status_code == 504
    assert exc_info.value.detail == "Timeout fetching image"
