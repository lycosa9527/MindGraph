"""GET /api/temp_images signed serve + COS hydrate."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from routers.api import helpers as url_helpers
from routers.api import png_export as png_mod


@pytest.fixture(autouse=True)
def _patch_jwt_secret() -> Iterator[None]:
    """Use a static HMAC key so signed-URL tests do not need Redis."""
    with patch.object(url_helpers, "get_jwt_secret", return_value="x" * 32):
        yield


def test_verify_signed_url_allow_expired() -> None:
    """Expired HMAC is rejected unless allow_expired is set."""
    signed = url_helpers.generate_signed_url("dingtalk_deadbeef_1.png", expiration_seconds=-10)
    query = signed.split("?", 1)[1]
    parts = dict(item.split("=", 1) for item in query.split("&"))
    exp = int(parts["exp"])
    assert url_helpers.verify_signed_url("dingtalk_deadbeef_1.png", parts["sig"], exp) is False
    assert (
        url_helpers.verify_signed_url(
            "dingtalk_deadbeef_1.png",
            parts["sig"],
            exp,
            allow_expired=True,
        )
        is True
    )


@pytest.mark.asyncio
async def test_serve_hydrates_and_accepts_expired_signature(tmp_path: Path) -> None:
    """COS-hydrated dingtalk PNGs stay visible after the signed exp."""
    filename = "dingtalk_deadbeef_1710000000.png"
    local = tmp_path / filename
    local.write_bytes(b"\x89PNG")
    signed = url_helpers.generate_signed_url(filename, expiration_seconds=-10)
    query = signed.split("?", 1)[1]
    parts = dict(item.split("=", 1) for item in query.split("&"))

    with patch.object(
        png_mod,
        "hydrate_dingtalk_temp_png",
        new=AsyncMock(return_value=local),
    ):
        response = await png_mod.serve_temp_image(filename, sig=parts["sig"], exp=int(parts["exp"]))
    assert response.path == str(local)
    assert response.media_type == "image/png"


@pytest.mark.asyncio
async def test_serve_rejects_bad_signature_even_when_file_exists(tmp_path: Path) -> None:
    """A present file is not enough without a valid HMAC."""
    filename = "dingtalk_deadbeef_1710000000.png"
    local = tmp_path / filename
    local.write_bytes(b"\x89PNG")
    with (
        patch.object(
            png_mod,
            "hydrate_dingtalk_temp_png",
            new=AsyncMock(return_value=local),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        await png_mod.serve_temp_image(filename, sig="not-a-real-sig", exp=9999999999)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_serve_does_not_hydrate_unsigned_requests(tmp_path: Path) -> None:
    """Unsigned URLs must not pull objects from COS."""
    filename = "dingtalk_deadbeef_1710000000.png"
    with (
        patch.object(png_mod, "TEMP_IMAGES_DIR", tmp_path),
        patch.object(png_mod, "hydrate_dingtalk_temp_png", new=AsyncMock()) as hydrate,
        pytest.raises(HTTPException) as exc_info,
    ):
        await png_mod.serve_temp_image(filename, sig=None, exp=None)
    hydrate.assert_not_called()
    assert exc_info.value.status_code == 404
