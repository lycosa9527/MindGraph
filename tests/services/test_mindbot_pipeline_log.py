"""Tests for services/mindbot/telemetry/pipeline_log.py."""

from __future__ import annotations

import logging

from services.mindbot.telemetry.pipeline_log import (
    clip_id,
    format_pipeline_ctx,
    get_pipeline_logger,
    session_webhook_host,
)


class TestClipId:
    """Tests for clip_id."""

    def test_none_returns_empty_string(self) -> None:
        assert clip_id(None) == ""

    def test_empty_string_returns_empty_string(self) -> None:
        assert clip_id("") == ""

    def test_whitespace_only_returns_empty_string(self) -> None:
        assert clip_id("   ") == ""

    def test_short_value_returned_unchanged(self) -> None:
        assert clip_id("abc-123") == "abc-123"

    def test_value_exactly_at_limit_returned_unchanged(self) -> None:
        value = "x" * 28
        assert clip_id(value) == value

    def test_long_value_truncated_with_ellipsis(self) -> None:
        value = "a" * 40
        result = clip_id(value)
        assert result.endswith("...")
        assert len(result) == 28

    def test_custom_max_len_respected(self) -> None:
        value = "a" * 20
        result = clip_id(value, max_len=10)
        assert result.endswith("...")
        assert len(result) == 10

    def test_strip_applied_before_length_check(self) -> None:
        assert clip_id("  hi  ") == "hi"


class TestFormatPipelineCtx:
    """Tests for format_pipeline_ctx."""

    def test_org_and_robot_always_present(self) -> None:
        result = format_pipeline_ctx(42, "robot-abc")
        assert "org=42" in result
        assert "robot=" in result

    def test_staff_and_nick_included_when_provided(self) -> None:
        result = format_pipeline_ctx(1, "r", staff_id="staff1", nick="Alice")
        assert "staff=staff1(Alice)" in result

    def test_staff_without_nick(self) -> None:
        result = format_pipeline_ctx(1, "r", staff_id="staff1")
        assert "staff=staff1" in result
        assert "(" not in result.split("staff=staff1")[1].split(" ")[0]

    def test_chat_type_and_conv_combined(self) -> None:
        result = format_pipeline_ctx(1, "r", chat_type="group", conv_dingtalk="conv123")
        assert "group:conv" in result

    def test_chat_type_without_conv(self) -> None:
        result = format_pipeline_ctx(1, "r", chat_type="1:1")
        assert "chat=1:1" in result

    def test_conv_without_chat_type(self) -> None:
        result = format_pipeline_ctx(1, "r", conv_dingtalk="conv123")
        assert "conv=conv" in result

    def test_no_dify_field_when_empty(self) -> None:
        result = format_pipeline_ctx(1, "r", dify_conv="")
        assert "dify=" not in result

    def test_dify_field_when_provided(self) -> None:
        result = format_pipeline_ctx(1, "r", dify_conv="dify-conv-id")
        assert "dify=dify-conv-id" in result

    def test_msg_id_included_when_provided(self) -> None:
        result = format_pipeline_ctx(1, "r", msg_id="msg-xyz")
        assert "msg=msg-xyz" in result

    def test_all_fields_combined(self) -> None:
        result = format_pipeline_ctx(
            99,
            "robot-1",
            msg_id="m1",
            staff_id="u1",
            nick="Bob",
            chat_type="group",
            conv_dingtalk="c1",
            dify_conv="d1",
        )
        assert "org=99" in result
        assert "staff=u1(Bob)" in result
        assert "group:c1" in result
        assert "msg=m1" in result
        assert "dify=d1" in result


class TestSessionWebhookHost:
    """Tests for session_webhook_host."""

    def test_valid_https_url_returns_netloc(self) -> None:
        assert session_webhook_host("https://hook.example.com/path?q=1") == "hook.example.com"

    def test_url_with_port_retains_port(self) -> None:
        assert session_webhook_host("http://internal.example.com:8080/cb") == "internal.example.com:8080"

    def test_empty_string_returns_question_mark(self) -> None:
        assert session_webhook_host("") == "?"

    def test_non_url_string_returns_question_mark(self) -> None:
        assert session_webhook_host("not a url") == "?"

    def test_none_like_raises_or_returns_question_mark(self) -> None:
        assert session_webhook_host("   ") == "?"


class TestGetPipelineLogger:
    """Tests for get_pipeline_logger."""

    def test_returns_logger_adapter(self) -> None:
        base = logging.getLogger("test.pipeline")
        adapter = get_pipeline_logger(base, org_id=1, msg_id="x")
        assert isinstance(adapter, logging.LoggerAdapter)

    def test_extra_fields_injected(self) -> None:
        base = logging.getLogger("test.pipeline2")
        adapter = get_pipeline_logger(base, org_id=7, msg_id="abc", error_code="OK", robot_code="r1")
        assert adapter.extra["mb_org_id"] == 7
        assert adapter.extra["mb_msg_id"] == "abc"
        assert adapter.extra["mb_error_code"] == "OK"
        assert adapter.extra["mb_robot_code"] == "r1"
