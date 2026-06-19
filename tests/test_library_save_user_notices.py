"""Tests for library save user-facing notices."""

from __future__ import annotations

from services.diagram.library_save_user_notices import (
    library_save_limit_notice,
    library_save_skip_user_notice,
    library_save_user_notice,
)


def test_library_save_limit_notice_zh() -> None:
    """Chinese limit notice is returned for zh language."""
    assert "图库已满" in library_save_limit_notice("zh")


def test_library_save_limit_notice_en() -> None:
    """English limit notice is returned for en language."""
    assert "library is full" in library_save_limit_notice("en").lower()


def test_dify_unbound_staff_en() -> None:
    """Dify audience unbound notice mentions bind DingTalk."""
    notice = library_save_user_notice("unbound_staff", "en", audience="dify")
    assert "bind DingTalk" in notice


def test_dingtalk_unbound_staff_zh() -> None:
    """DingTalk audience uses teacher-friendly bind path."""
    notice = library_save_user_notice("unbound_staff", "zh", audience="dingtalk")
    assert "绑定钉钉" in notice
    assert "X-MG-Dify-User" not in notice


def test_dify_no_user_mentions_header() -> None:
    """Dify no_user notice mentions X-MG-Dify-User."""
    notice = library_save_user_notice("no_user", "zh", audience="dify")
    assert "X-MG-Dify-User" in notice


def test_dingtalk_no_user_admin_guidance() -> None:
    """DingTalk no_user notice points to administrator."""
    notice = library_save_user_notice("no_user", "en", audience="dingtalk")
    assert "administrator" in notice.lower()
    assert "X-MG-Dify-User" not in notice


def test_limit_reached_via_user_notice() -> None:
    """limit_reached returns limit notice for both audiences."""
    assert "图库已满" in library_save_user_notice("limit_reached", "zh", audience="dingtalk")


def test_skip_user_notice_excludes_limit() -> None:
    """Legacy helper skips limit_reached."""
    assert library_save_skip_user_notice("limit_reached", "en") == ""
    assert library_save_skip_user_notice(None, "en") == ""
