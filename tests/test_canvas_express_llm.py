"""Canvas Express stays on DashScope deepseek-v4.1-flash."""

import pytest

from config.settings import config
from services.infrastructure.utils.ark_thinking import volcengine_thinking_extra
from services.infrastructure.utils.load_balancer import LLMLoadBalancer
from services.llm.llm_utils import stream_enable_thinking


def test_express_payload_uses_dashscope_flash_model() -> None:
    """Express requests name the DashScope flash model and keep thinking off."""
    payload = config.get_llm_data("topic", "express")
    assert payload["model"] == "deepseek-v4.1-flash"
    assert payload["model"] == config.EXPRESS_MODEL
    assert payload["extra_body"]["enable_thinking"] is False
    assert LLMLoadBalancer.FIXED_MODEL_MAP["express"] == "express"
    assert LLMLoadBalancer().get_provider_from_model("express") == "dashscope"
    assert stream_enable_thinking("express") is False
    assert config.DEEPSEEK_MODEL == "deepseek-v4.1-flash"


def test_volcengine_v4_thinking_switch() -> None:
    """Ark DeepSeek-V4.1 must be told to think or not; older flags do not count."""
    assert volcengine_thinking_extra("ark-deepseek", False) == {"thinking": {"type": "disabled"}}
    assert volcengine_thinking_extra("ark-deepseek", True) == {"thinking": {"type": "enabled"}}
    assert not volcengine_thinking_extra("ark-doubao", False)
    assert volcengine_thinking_extra("ark-kimi", True) == {"enable_thinking": True}
    assert volcengine_thinking_extra("ark-doubao21", False) == {"thinking": {"type": "disabled"}}
    assert LLMLoadBalancer.FIXED_MODEL_MAP["doubao21"] == "ark-doubao21"
    assert LLMLoadBalancer.FIXED_MODEL_MAP["qwen3.7-plus"] == "qwen3.7-plus"
    assert LLMLoadBalancer.FIXED_MODEL_MAP["qwen3-max"] == "qwen3-max"
    assert LLMLoadBalancer.FIXED_MODEL_MAP["kimi"] == "ark-kimi"
    assert LLMLoadBalancer.FIXED_MODEL_MAP["qwen3.8-flash"] == "qwen3.8-flash"


def test_canvas_model_ids_come_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Canvas Doubao and GLM Flash use env model ids and invent none."""
    monkeypatch.setenv("DOUBAO_MODEL", "doubao-seed-2-1-turbo-260628")
    monkeypatch.setenv("GLM_FLASH_MODEL", "glm-5-3-flash-260828")
    config.refresh_env_cache()
    try:
        assert config.DOUBAO_MODEL == "doubao-seed-2-1-turbo-260628"
        assert config.GLM_FLASH_MODEL == "glm-5-3-flash-260828"
        monkeypatch.setenv("DOUBAO_MODEL", "  ep-example  ")
        config.refresh_env_cache()
        assert config.DOUBAO_MODEL == "ep-example"
        monkeypatch.delenv("DOUBAO_MODEL", raising=False)
        monkeypatch.delenv("GLM_FLASH_MODEL", raising=False)
        config.refresh_env_cache()
        assert config.DOUBAO_MODEL == ""
        assert config.GLM_FLASH_MODEL == ""
    finally:
        config.refresh_env_cache()
