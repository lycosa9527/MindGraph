"""Tests for Dify user key parsing."""

from utils.dify_user_key import parse_mg_user_id, parse_mindbot_dify_key


def test_parse_mg_user_id() -> None:
    assert parse_mg_user_id("mg_user_42") == 42
    assert parse_mg_user_id("mg_user_0") is None
    assert parse_mg_user_id("other") is None


def test_parse_mindbot_dify_key_with_underscore_staff() -> None:
    org, staff = parse_mindbot_dify_key("mindbot_5_manager7439")
    assert org == 5
    assert staff == "manager7439"

    org2, staff2 = parse_mindbot_dify_key("mindbot_5_a_b_c")
    assert org2 == 5
    assert staff2 == "a_b_c"
