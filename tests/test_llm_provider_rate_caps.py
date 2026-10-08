"""App rate caps follow the confirmed DashScope and Volcengine quotas."""

from typing import cast

from config.rate_limiting import (
    DASHSCOPE_DEEPSEEK_QPM_DEFAULT,
    DEEPSEEK_VOLCENGINE_QPM_DEFAULT,
    QWEN38_DASHSCOPE_QPM_DEFAULT,
    QWEN_DASHSCOPE_QPM_DEFAULT,
)
from services.infrastructure.rate_limiting.dashscope_model_limiters import set_dashscope_model_limiters
from services.infrastructure.rate_limiting.rate_limiter import DashscopeRateLimiter
from services.infrastructure.utils.llm_routing_store import clear_overrides_for_tests
from services.llm.llm_utils import LLMUtils


class _Limiter:
    """Stand-in with the enabled flag get_rate_limiter checks."""

    def __init__(self) -> None:
        self.enabled = True


def setup_function() -> None:
    """Do not leak limiters or routing overrides into other tests."""
    set_dashscope_model_limiters(None, None)
    clear_overrides_for_tests()


def teardown_function() -> None:
    """Clear the process holder."""
    set_dashscope_model_limiters(None, None)
    clear_overrides_for_tests()


def test_defaults_match_confirmed_provider_rpm() -> None:
    """90% of Beijing DashScope and the Volcengine DeepSeek-V4-Flash console quota."""
    assert DASHSCOPE_DEEPSEEK_QPM_DEFAULT == 13500
    assert QWEN_DASHSCOPE_QPM_DEFAULT == 27000
    assert QWEN38_DASHSCOPE_QPM_DEFAULT == 13500
    assert DEEPSEEK_VOLCENGINE_QPM_DEFAULT == 450


def test_qwen_express_and_deepseek_use_separate_windows() -> None:
    """qwen3.6-flash must not spend the deepseek-v4.1-flash DashScope window."""
    shared = _Limiter()
    qwen = _Limiter()
    qwen38 = _Limiter()
    set_dashscope_model_limiters(
        cast(DashscopeRateLimiter, qwen),
        cast(DashscopeRateLimiter, qwen38),
    )
    assert LLMUtils.get_rate_limiter("qwen", "qwen", "dashscope", shared, None, None, None) is qwen
    assert LLMUtils.get_rate_limiter("express", "express", "dashscope", shared, None, None, None) is shared
    assert LLMUtils.get_rate_limiter("deepseek", "deepseek", "dashscope", shared, None, None, None) is shared
    assert LLMUtils.get_rate_limiter("qwen", "qwen3.8-flash", "dashscope", shared, None, None, None) is qwen38
    doubao = _Limiter()
    assert LLMUtils.get_rate_limiter("doubao21", "ark-doubao21", "volcengine", shared, None, None, doubao) is doubao
    assert LLMUtils.get_rate_limiter("qwen3.7-plus", "qwen3.7-plus", "dashscope", shared, None, None, None) is qwen
