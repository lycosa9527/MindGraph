"""Tests for DingTalk inbound media download code extraction."""

from services.mindbot.platforms.dingtalk.inbound.parser import (
    extract_download_code_candidates,
    extract_download_code_for_openapi,
)


def test_picture_prefers_content_download_code_over_picture_download_code() -> None:
    """OpenAPI expects content.downloadCode; pictureDownloadCode is a legacy alias."""
    body = {
        "msgtype": "picture",
        "content": {
            "downloadCode": "code-for-openapi",
            "pictureDownloadCode": "legacy-picture-code",
        },
    }
    assert extract_download_code_for_openapi(body, "picture") == "code-for-openapi"
    assert extract_download_code_candidates(body, "picture") == [
        "code-for-openapi",
        "legacy-picture-code",
    ]


def test_picture_falls_back_to_picture_download_code() -> None:
    """When only pictureDownloadCode is present, still return a usable code."""
    body = {
        "msgtype": "picture",
        "content": {"pictureDownloadCode": "legacy-only"},
    }
    assert extract_download_code_for_openapi(body, "picture") == "legacy-only"


def test_video_download_code_from_nested_object() -> None:
    """Video payloads nest downloadCode under the video object."""
    body = {
        "msgtype": "video",
        "video": {"downloadCode": "video-code"},
    }
    assert extract_download_code_for_openapi(body, "video") == "video-code"
