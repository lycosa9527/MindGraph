"""Tests for DashScope workspace MaaS URL builders."""

from __future__ import annotations

from config.dashscope_urls import (
    build_chat_completions_url,
    build_dashscope_inference_ws_url,
    build_realtime_ws_base,
    dashscope_endpoint_summary,
    normalize_dashscope_region,
    resolve_chat_completions_url,
    resolve_realtime_ws_base,
)


def test_normalize_dashscope_region_aliases() -> None:
    """Region env aliases map to canonical keys."""
    assert normalize_dashscope_region("cn") == "cn-beijing"
    assert normalize_dashscope_region("sg") == "ap-southeast-1"
    assert normalize_dashscope_region("intl") == "ap-southeast-1"
    assert normalize_dashscope_region("tokyo") == "ap-northeast-1"


def test_build_workspace_beijing_chat_url() -> None:
    """Beijing workspace uses cn-beijing.maas.aliyuncs.com."""
    url = build_chat_completions_url(
        workspace_id="ws-test123",
        region="cn-beijing",
    )
    assert url == ("https://ws-test123.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions")


def test_build_workspace_singapore_chat_url() -> None:
    """Singapore workspace uses ap-southeast-1 MaaS host."""
    url = build_chat_completions_url(
        workspace_id="ws-test123",
        region="ap-southeast-1",
    )
    assert "ap-southeast-1.maas.aliyuncs.com" in url


def test_us_region_ignores_workspace_subdomain() -> None:
    """US endpoint stays on dashscope-us.aliyuncs.com."""
    url = build_chat_completions_url(
        workspace_id="ws-test123",
        region="us",
    )
    assert url.startswith("https://dashscope-us.aliyuncs.com/compatible-mode/v1/")


def test_explicit_qwen_api_url_wins() -> None:
    """Explicit QWEN_API_URL overrides workspace builder."""
    explicit = "https://custom.example/v1/chat/completions"
    resolved = resolve_chat_completions_url(
        explicit_url=explicit,
        workspace_id="ws-test123",
        region="cn-beijing",
    )
    assert resolved == explicit


def test_legacy_when_no_workspace_and_no_explicit() -> None:
    """Default remains legacy Beijing dashscope host."""
    summary = dashscope_endpoint_summary(
        explicit_chat_url=None,
        explicit_api_v1=None,
        workspace_id=None,
        region_raw="cn-beijing",
    )
    assert summary["mode"] == "legacy"
    assert "dashscope.aliyuncs.com" in summary["chat_completions_url"]


def test_workspace_mode_summary() -> None:
    """Workspace id selects workspace mode."""
    summary = dashscope_endpoint_summary(
        explicit_chat_url=None,
        explicit_api_v1=None,
        workspace_id="ws-abc",
        region_raw="cn-beijing",
    )
    assert summary["mode"] == "workspace"
    assert summary["workspace_id"] == "ws-abc"
    assert "ws-abc.cn-beijing.maas.aliyuncs.com" in summary["chat_completions_url"]
    assert "wss://ws-abc.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime" == summary["realtime_ws_base"]


def test_build_workspace_realtime_ws_url() -> None:
    """Realtime WebSocket uses the same workspace host as HTTP."""
    ws_base = build_realtime_ws_base(
        workspace_id="llm-9b85qukeq1cjfa5l",
        region="cn-beijing",
    )
    assert ws_base == ("wss://llm-9b85qukeq1cjfa5l.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime")


def test_explicit_realtime_ws_wins() -> None:
    """Explicit DASHSCOPE_REALTIME_WS_BASE overrides workspace builder."""
    explicit = "wss://custom.example/api-ws/v1/realtime"
    resolved = resolve_realtime_ws_base(
        explicit_url=explicit,
        workspace_id="llm-9b85qukeq1cjfa5l",
        region="cn-beijing",
    )
    assert resolved == explicit


def test_build_dashscope_inference_ws_url() -> None:
    """MaaS inference WS is shared by Fun-ASR and CosyVoice realtime."""
    url = build_dashscope_inference_ws_url(
        workspace_id="ws-test123",
        region="cn-beijing",
    )
    assert url == "wss://ws-test123.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
