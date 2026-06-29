"""Tests for SmartEdu URL parsing."""

from __future__ import annotations

import pytest

from file_reader.smartedu.url_parser import SmartEduUrlKind, parse_smartedu_url


def test_parse_class_activity_url() -> None:
    url = (
        "https://basic.smartedu.cn/syncClassroom/classActivity"
        "?activityId=b45c766e-e428-3d16-c04c-022cf976fc7e"
        "&chapterId=5b1c7673-8e1c-419b-b378-4d4562265edc"
    )
    parsed = parse_smartedu_url(url)
    assert parsed.kind is SmartEduUrlKind.CLASS_ACTIVITY
    assert parsed.resource_id == "b45c766e-e428-3d16-c04c-022cf976fc7e"
    assert parsed.detail_url.endswith("/b45c766e-e428-3d16-c04c-022cf976fc7e.json")


def test_parse_tch_material_url() -> None:
    url = (
        "https://basic.smartedu.cn/tchMaterial/detail"
        "?contentType=assets_document&contentId=abc12345-1234-1234-1234-123456789abc"
    )
    parsed = parse_smartedu_url(url)
    assert parsed.kind is SmartEduUrlKind.TCH_MATERIAL
    assert parsed.resource_id == "abc12345-1234-1234-1234-123456789abc"
    assert "/resources/tch_material/details/" in parsed.detail_url


def test_invalid_url_raises() -> None:
    with pytest.raises(ValueError):
        parse_smartedu_url("https://example.com/page")
