"""Tests for library save user-facing notices."""

from __future__ import annotations

from services.diagram.library_save_user_notices import (
    library_save_limit_notice,
    library_save_skip_user_notice,
    library_save_user_notice,
    notice_audience_for_dify_key,
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


def test_notice_audience_for_dify_key() -> None:
    """MindBot keys map to dingtalk; web/guest map to mindmate."""
    assert notice_audience_for_dify_key("mindbot_5_staff") == "dingtalk"
    assert notice_audience_for_dify_key("mg_user_7") == "mindmate"
    assert notice_audience_for_dify_key("guest_abc") == "mindmate"
    assert notice_audience_for_dify_key("") == "mindmate"


def test_skip_user_notice_mindmate_no_ops_header() -> None:
    """Embedded chat notice for web must not mention X-MG-Dify-User."""
    notice = library_save_skip_user_notice("no_user", "en", dify_user_key="")
    assert "administrator" in notice.lower() or "regenerat" in notice.lower()
    assert "X-MG-Dify-User" not in notice


def test_skip_user_notice_guest_login() -> None:
    """Guest preview notice asks to sign in."""
    notice = library_save_skip_user_notice("no_user", "en", dify_user_key="guest_1")
    assert "sign in" in notice.lower()
    assert "X-MG-Dify-User" not in notice


def test_mindmate_no_user_audience() -> None:
    """Explicit mindmate audience omits ops header guidance."""
    notice = library_save_user_notice("no_user", "zh", audience="mindmate")
    assert "联系管理员" in notice or "重新生成" in notice
    assert "X-MG-Dify-User" not in notice
