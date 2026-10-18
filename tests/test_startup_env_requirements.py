"""Startup refuses to listen when required .env values are still samples."""

from __future__ import annotations

import pytest

from services.infrastructure.lifecycle import startup_env_requirements as gate
from services.infrastructure.utils.launch_commands import lines_startup_env_hint

_FLAGS_OFF = (
    "FEATURE_MINDMATE",
    "FEATURE_SMART_RESPONSE",
    "FEATURE_WECHAT_LOGIN",
    "FEATURE_DINGTALK_LOGIN",
    "FEATURE_MARKETS",
    "FEATURE_VOD",
    "FEATURE_WORKSHOP_CHAT",
)


def _ready_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A .env that satisfies the startup gate."""
    monkeypatch.setenv("DEBUG", "True")
    monkeypatch.setenv("AUTH_MODE", "standard")
    monkeypatch.setenv("CAPTCHA_PROVIDER", "legacy")
    monkeypatch.setenv("DATABASE_URL", "postgresql://mindgraph_user:pw@localhost:5432/mindgraph")
    monkeypatch.setenv("QWEN_API_KEY", "sk-test-key")
    monkeypatch.setenv("DASHSCOPE_WORKSPACE_ID", "llm-testworkspace")
    monkeypatch.delenv("QWEN_API_URL", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_URL", raising=False)
    monkeypatch.setenv("ARK_API_KEY", "ark-test-key")
    monkeypatch.setenv("ARK_DEEPSEEK_ENDPOINT", "ep-real-deepseek")
    monkeypatch.setenv("ARK_DOUBAO_ENDPOINT", "ep-real-doubao")
    monkeypatch.setenv("GLM_FLASH_MODEL", "glm-5-3-flash-260828")
    monkeypatch.setenv("DOUBAO_MODEL", "doubao-seed-2-1-turbo-260628")
    monkeypatch.setenv("MINDMATE_DIFY_USER_PREFIX", "dev_roy")
    for name in _FLAGS_OFF:
        monkeypatch.setenv(name, "False")


def _titles(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    _ready_env(monkeypatch)
    return [gap.title for gap in gate.collect_startup_env_gaps()]


def test_ready_env_has_no_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    """A filled local .env is allowed to start."""
    assert _titles(monkeypatch) == []


def test_llm_samples_are_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """env.example placeholders for DashScope and Volcengine are called out together."""
    _ready_env(monkeypatch)
    monkeypatch.setenv("QWEN_API_KEY", "your-workspace-api-key-here")
    monkeypatch.setenv("DASHSCOPE_WORKSPACE_ID", "llm-your-workspace-id")
    monkeypatch.setenv("ARK_API_KEY", "")
    monkeypatch.setenv("ARK_DEEPSEEK_ENDPOINT", "ep-20250101000000-dummy")
    text = "\n".join(gate.startup_env_requirement_lines())
    assert "LLM" in text
    assert "QWEN_API_KEY" in text
    assert "DASHSCOPE_WORKSPACE_ID" in text
    assert "ARK_API_KEY" in text
    assert "ARK_DEEPSEEK_ENDPOINT" in text
    assert "cannot start" in text
    assert "cp env.example .env" in text


def test_explicit_qwen_url_skips_workspace_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A legacy QWEN_API_URL stands in for the workspace id."""
    _ready_env(monkeypatch)
    monkeypatch.setenv("DASHSCOPE_WORKSPACE_ID", "")
    monkeypatch.setenv("QWEN_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
    assert gate.collect_startup_env_gaps() == []


def test_mindmate_template_prefix_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """dev_yourname is the sample, not a personal install name."""
    _ready_env(monkeypatch)
    monkeypatch.setenv("MINDMATE_DIFY_USER_PREFIX", "dev_yourname")
    gaps = gate.collect_startup_env_gaps()
    assert [gap.title for gap in gaps] == ["MindMate user id"]
    joined = "\n".join(gaps[0].lines)
    assert "dev_yourname" in gaps[0].lines[0]
    assert "MINDMATE_DIFY_USER_PREFIX=dev_yourname" not in joined
    assert "MINDMATE_DIFY_USER_PREFIX=dev_roy" in joined


def test_feature_flags_name_the_missing_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each enabled flag tells the operator which .env keys to set, or how to turn it off."""
    _ready_env(monkeypatch)
    monkeypatch.setenv("FEATURE_MINDMATE", "True")
    monkeypatch.setenv("DIFY_API_KEY", "your_dify_api_key_here")
    monkeypatch.setenv("DIFY_API_URL", "")
    monkeypatch.setenv("FEATURE_SMART_RESPONSE", "True")
    monkeypatch.setenv("DEVICE_REGISTRATION_SECRET", "")
    monkeypatch.setenv("FEATURE_WECHAT_LOGIN", "True")
    monkeypatch.setenv("WECHAT_OAUTH_APP_ID", "")
    monkeypatch.setenv("WECHAT_OAUTH_APP_SECRET", "")
    monkeypatch.setenv("EXTERNAL_BASE_URL", "")
    monkeypatch.setenv("FEATURE_MARKETS", "True")
    monkeypatch.setenv("ALIPAY_APP_ID", "")
    monkeypatch.setenv("ALIPAY_NOTIFY_BASE_URL", "")
    monkeypatch.setenv("ALIPAY_APP_PRIVATE_KEY", "")
    monkeypatch.setenv("ALIPAY_ALIPAY_PUBLIC_KEY", "")
    monkeypatch.setenv("FEATURE_VOD", "True")
    monkeypatch.setenv("TENCENT_VOD_APP_ID", "")
    monkeypatch.setenv("TENCENT_VOD_PLAY_KEY", "")
    monkeypatch.setenv("TENCENT_VOD_SECRET_ID", "")
    monkeypatch.setenv("TENCENT_VOD_SECRET_KEY", "")
    monkeypatch.setenv("FEATURE_WORKSHOP_CHAT", "True")
    monkeypatch.setenv("WS_REDIS_FANOUT_ENABLED", "true")
    monkeypatch.delenv("COLLAB_FANOUT_ORIGIN_SECRET", raising=False)
    titles = [gap.title for gap in gate.collect_startup_env_gaps()]
    assert titles == [
        "FEATURE_MINDMATE",
        "FEATURE_SMART_RESPONSE",
        "FEATURE_MARKETS",
        "FEATURE_VOD",
        "FEATURE_WORKSHOP_CHAT",
        "FEATURE_WECHAT_LOGIN",
        "OAuth public URL",
    ]


def test_production_captcha_and_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-debug startup names T-Sec and DATABASE_URL when they are missing."""
    _ready_env(monkeypatch)
    monkeypatch.setenv("DEBUG", "False")
    monkeypatch.setenv("CAPTCHA_PROVIDER", "tsec")
    monkeypatch.setenv("TENCENT_CAPTCHA_APP_ID", "")
    monkeypatch.setenv("TENCENT_CAPTCHA_APP_SECRET_KEY", "")
    monkeypatch.setenv("TENCENT_SMS_SECRET_ID", "your-tencent-secret-id-here")
    monkeypatch.setenv("TENCENT_SMS_SECRET_KEY", "your-tencent-secret-key-here")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    titles = [gap.title for gap in gate.collect_startup_env_gaps()]
    assert titles == ["Database", "Captcha"]


def test_debug_skips_captcha_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Debug keeps the SVG captcha when T-Sec keys are empty."""
    _ready_env(monkeypatch)
    monkeypatch.setenv("DEBUG", "True")
    monkeypatch.setenv("CAPTCHA_PROVIDER", "tsec")
    monkeypatch.setenv("TENCENT_CAPTCHA_APP_ID", "")
    assert gate.collect_startup_env_gaps() == []


def test_enforce_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    """The launcher path exits instead of continuing with a half-configured process."""
    _ready_env(monkeypatch)
    monkeypatch.setenv("QWEN_API_KEY", "")
    with pytest.raises(SystemExit) as caught:
        gate.enforce_startup_env_requirements_or_exit()
    assert caught.value.code == 1


def test_launch_cheatsheet_lists_env_keys() -> None:
    """The copy-paste sheet includes the same .env names the banner uses."""
    text = "\n".join(lines_startup_env_hint())
    assert "QWEN_API_KEY" in text
    assert "MINDMATE_DIFY_USER_PREFIX" in text
    assert "FEATURE_MARKETS=True" in text
    assert "DEVICE_REGISTRATION_SECRET" in text
