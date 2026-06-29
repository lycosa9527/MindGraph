"""Tests for SmartEdu probe status hints."""

from __future__ import annotations

from file_reader.platform_browser.models import ProbeContext
from file_reader.platform_browser.smartedu_extractor import smartedu_probe_status_hint


def test_smartedu_probe_status_hint_requires_token() -> None:
    """Missing token shows a token hint."""
    context = ProbeContext(
        page_url=(
            "https://basic.smartedu.cn/syncClassroom/classActivity"
            "?activityId=b45c766e-1234-5678-9abc-def012345678"
        ),
        login_state={},
        cookies=[],
        smartedu_token="",
    )
    assert smartedu_probe_status_hint(context, ()) == "smartedu_token_required"


def test_smartedu_probe_status_hint_requires_lesson_page() -> None:
    """Non-lesson SmartEdu pages show a lesson hint."""
    context = ProbeContext(
        page_url="https://basic.smartedu.cn/",
        login_state={},
        cookies=[],
        smartedu_token="saved",
    )
    assert smartedu_probe_status_hint(context, ()) == "smartedu_lesson_required"
