"""Tests for WeChat Channels capture helpers."""

from __future__ import annotations

from file_reader.wechat_channels.decrypt import decrypt_channels_video
from file_reader.wechat_channels.url_parser import (
    is_channels_media_url,
    is_channels_page,
    merge_channels_captures,
    parse_channels_capture_entry,
)


def test_is_channels_page() -> None:
    """Channels host is recognized."""
    assert is_channels_page("https://channels.weixin.qq.com/web/pages/feed")


def test_is_channels_media_url() -> None:
    """Tencent stodownload URLs are recognized."""
    url = "https://finder.video.qq.com/251/20302/stodownload?encfilekey=abc"
    assert is_channels_media_url(url) is True


def test_parse_channels_capture_entry() -> None:
    """Hook JSON entries become captured videos."""
    entry = {
        "video_id": "abc",
        "title": "demo",
        "media_url": "https://finder.video.qq.com/251/20302/stodownload?encfilekey=abc",
        "decode_key": "123",
    }
    parsed = parse_channels_capture_entry(entry)
    assert parsed is not None
    assert parsed.decode_key == "123"


def test_merge_channels_captures_deduplicates() -> None:
    """Duplicate captures are merged."""
    first = merge_channels_captures(
        (),
        hook_raw=[
            {
                "video_id": "abc",
                "title": "demo",
                "media_url": "https://finder.video.qq.com/251/20302/stodownload?encfilekey=abc",
                "decode_key": "123",
            }
        ],
    )
    second = merge_channels_captures(
        first,
        hook_raw=[
            {
                "video_id": "abc",
                "title": "demo",
                "media_url": "https://finder.video.qq.com/251/20302/stodownload?encfilekey=abc",
                "decode_key": "123",
            }
        ],
    )
    assert len(second) == 1


def test_decrypt_channels_video_xor() -> None:
    """Encrypted header bytes are XOR-decrypted."""
    keystream = bytes(range(16)) + bytes(16)
    encrypted = bytes(value ^ keystream[index] for index, value in enumerate(b"0123456789abcdef"))
    decrypted = decrypt_channels_video(encrypted + b"tail", keystream)
    assert decrypted.startswith(b"0123456789abcdef")
    assert decrypted.endswith(b"tail")
