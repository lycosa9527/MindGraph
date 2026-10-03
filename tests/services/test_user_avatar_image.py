"""Photo avatar normalization and COS URL ownership."""

from io import BytesIO

import pytest
from PIL import Image

from services.auth import user_avatar_image as avatar_image


def test_normalize_avatar_png_is_a_512_circle():
    """Center-crop and circular alpha land on a 512 PNG."""
    source = Image.new("RGB", (800, 400), (255, 0, 0))
    raw = BytesIO()
    source.save(raw, format="PNG")

    out = avatar_image.normalize_avatar_png(raw.getvalue())

    with Image.open(BytesIO(out)) as image:
        assert image.size == (512, 512)
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (255, 0, 0, 0)
        assert image.getpixel((256, 256)) == (255, 0, 0, 255)


def test_normalize_avatar_png_rejects_non_images():
    """Bytes that are not an image are rejected before upload."""
    with pytest.raises(avatar_image.AvatarImageError) as raised:
        avatar_image.normalize_avatar_png(b"not-an-image")
    assert raised.value.code == "invalid"


def test_local_dev_avatar_falls_back_to_emoji(monkeypatch):
    """Development hosts show the brand cat instead of a stored COS URL."""
    url = "https://demo.cos.ap-beijing.myqcloud.com/dev/avatars/users/7.png?v=1"
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert avatar_image.avatar_for_client(url) == "🐈‍⬛"
    assert avatar_image.avatar_for_client("😀") == "😀"
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert avatar_image.avatar_for_client(url) == url


def test_public_avatar_url_round_trip(monkeypatch):
    """Only this bucket's avatar URL maps back to its object key."""
    monkeypatch.setattr(avatar_image, "COS_BUCKET", "demo-1250000000")
    monkeypatch.setattr(avatar_image, "COS_REGION", "ap-beijing")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)

    key = avatar_image.user_avatar_object_key(7)
    url = f"{avatar_image.public_avatar_url(key)}?v=9"

    assert avatar_image.stored_avatar_object_key(url) == key
    assert avatar_image.stored_avatar_object_key("🐈‍⬛") is None
    assert avatar_image.stored_avatar_object_key("https://evil.example/dev/avatars/users/7.png") is None
