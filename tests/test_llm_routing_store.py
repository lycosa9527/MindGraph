"""Live LLM routing overrides and the admin traffic diagram."""

import pytest

from config.settings import config
from services.infrastructure.utils.llm_routing_store import (
    accumulate_token_rows,
    build_llm_control_view,
    clear_overrides_for_tests,
    env_value,
    normalize_updates,
    replace_overrides,
    token_bucket,
)


def setup_function() -> None:
    """Each test starts from the environment, with no process override."""
    clear_overrides_for_tests()


def teardown_function() -> None:
    """Do not leak overrides into later tests."""
    clear_overrides_for_tests()


def test_normalize_rejects_bad_values_and_clears_env_match() -> None:
    """Endpoints must be real Ark ids, and an env match is a clear."""
    with pytest.raises(ValueError, match="invalid_value"):
        normalize_updates({"ARK_DEEPSEEK_ENDPOINT": "ep-20250101000000-dummy"})
    with pytest.raises(ValueError, match="invalid_value"):
        normalize_updates({"DEEPSEEK_MODEL": "has space"})
    with pytest.raises(ValueError, match="unknown_field"):
        normalize_updates({"ARK_API_KEY": "secret"})
    cleared = normalize_updates({"EXPRESS_MODEL": env_value("EXPRESS_MODEL")})
    assert cleared["EXPRESS_MODEL"] is None
    kept = normalize_updates({"QWEN_MODEL_GENERATION": "qwen-admin-test"})
    assert kept["QWEN_MODEL_GENERATION"] == "qwen-admin-test"


def test_token_buckets_follow_provider() -> None:
    """DeepSeek usage splits by provider. Other aliases stay on one leg."""
    assert token_bucket("deepseek", "dashscope") == "deepseek_dashscope"
    assert token_bucket("deepseek", "volcengine") == "deepseek_volcengine"
    assert token_bucket("ark-deepseek", "volcengine") == "deepseek_volcengine"
    assert token_bucket("express", "dashscope") == "express"
    assert token_bucket("qwen3.6-flash", "dashscope") == "qwen"
    assert token_bucket("qwen3.8-flash", "dashscope") == "qwen38"
    assert token_bucket("doubao", "volcengine") == "doubao"
    assert token_bucket("doubao21", "volcengine") == "doubao"
    assert token_bucket("mystery", "dashscope") is None


def test_diagram_uses_override_and_sums_tokens() -> None:
    """The DeepSeek split shows the live model name and both token legs."""
    replace_overrides({"DEEPSEEK_MODEL": "deepseek-v4-pro", "ARK_DOUBAO_ENDPOINT": "ep-20260101010101-abcde"})
    tokens = accumulate_token_rows(
        [
            ("deepseek", "dashscope", 10, 1),
            ("deepseek", "volcengine", 4, 1),
            ("ark-deepseek", "volcengine", 6, 2),
            ("express", "dashscope", 3, 1),
            ("qwen", "dashscope", 8, 1),
            ("doubao", "volcengine", 2, 1),
            ("kimi", "volcengine", 1, 1),
            ("other", "dashscope", 100, 9),
        ]
    )
    view = build_llm_control_view(
        tokens=tokens,
        redis_ok=True,
        tokens_ok=True,
        weights={"dashscope": 75, "volcengine": 25},
        balancing_enabled=True,
        strategy="weighted",
        app_rpm={
            "deepseek_dashscope": 13500,
            "express": 13500,
            "deepseek_volcengine": 450,
            "qwen": 27000,
            "qwen38": 13500,
            "doubao": 27000,
            "kimi": 4500,
        },
    )
    routes = view["routes"]
    assert isinstance(routes, list)
    deepseek = routes[0]
    assert isinstance(deepseek, dict)
    legs = deepseek["legs"]
    assert isinstance(legs, list)
    dash_leg = legs[0]
    volc_leg = legs[1]
    assert isinstance(dash_leg, dict)
    assert isinstance(volc_leg, dict)
    assert view["strategy"] == "weighted"
    assert dash_leg["target"] == "deepseek-v4-pro"
    assert dash_leg["app_rpm"] == 13500
    assert dash_leg["provider_rpm"] == 15000
    assert dash_leg["shares_app_rpm"] is True
    assert volc_leg["app_rpm"] == 450
    assert volc_leg["provider_rpm"] == 500
    assert dash_leg["tokens"] == 10
    assert volc_leg["tokens"] == 10
    assert volc_leg["requests"] == 3
    doubao = next(route for route in routes if isinstance(route, dict) and route.get("id") == "doubao")
    assert isinstance(doubao, dict)
    doubao_legs = doubao["legs"]
    assert isinstance(doubao_legs, list)
    doubao_leg = doubao_legs[0]
    assert isinstance(doubao_leg, dict)
    assert doubao_leg["target"] == "ep-20260101010101-abcde"


def test_config_properties_read_the_process_override() -> None:
    """A pasted DashScope id or Volcengine endpoint is what the next request sends."""
    pasted = normalize_updates(
        {
            "DEEPSEEK_MODEL": "deepseek-pasted-id",
            "EXPRESS_MODEL": "deepseek-pasted-express",
            "QWEN_MODEL_GENERATION": "qwen-pasted-gen",
            "QWEN_MODEL_CLASSIFICATION": "qwen-pasted-cls",
            "ARK_DEEPSEEK_ENDPOINT": "ep-20260303030303-paste1",
            "ARK_DOUBAO_ENDPOINT": "ep-20260303030303-paste2",
            "ARK_KIMI_ENDPOINT": "ep-20260202020202-zzzzz",
        }
    )
    assert pasted["ARK_DEEPSEEK_ENDPOINT"] == "ep-20260303030303-paste1"
    replace_overrides({key: value for key, value in pasted.items() if value})
    assert config.DEEPSEEK_MODEL == "deepseek-pasted-id"
    assert config.EXPRESS_MODEL == "deepseek-pasted-express"
    assert config.QWEN_MODEL_GENERATION == "qwen-pasted-gen"
    assert config.QWEN_MODEL_CLASSIFICATION == "qwen-pasted-cls"
    assert config.QWEN_MODEL_NODE_EXPLAIN == env_value("QWEN_MODEL_NODE_EXPLAIN")
    assert config.ARK_DEEPSEEK_ENDPOINT == "ep-20260303030303-paste1"
    assert config.ARK_DOUBAO_ENDPOINT == "ep-20260303030303-paste2"
    assert config.ARK_KIMI_ENDPOINT == "ep-20260202020202-zzzzz"
    assert config.get_llm_data("hello", "express")["model"] == "deepseek-pasted-express"
    assert config.get_llm_data("hello", "deepseek")["model"] == "deepseek-pasted-id"
    assert config.get_qwen_generation_data("hello")["model"] == "qwen-pasted-gen"
    assert config.get_qwen_classification_data("hello")["model"] == "qwen-pasted-cls"
    view = build_llm_control_view(
        tokens={},
        redis_ok=True,
        tokens_ok=True,
        weights={"dashscope": 75, "volcengine": 25},
        balancing_enabled=True,
        strategy="weighted",
        app_rpm={},
    )
    routes = view["routes"]
    assert isinstance(routes, list)
    qwen38 = next(route for route in routes if isinstance(route, dict) and route.get("id") == "qwen38")
    assert isinstance(qwen38, dict)
    legs = qwen38["legs"]
    assert isinstance(legs, list)
    leg = legs[0]
    assert isinstance(leg, dict)
    assert leg["target"] == "qwen3.8-flash"
    clear_overrides_for_tests()
    assert config.DEEPSEEK_MODEL == env_value("DEEPSEEK_MODEL")
    assert config.QWEN_MODEL_NODE_EXPLAIN == env_value("QWEN_MODEL_NODE_EXPLAIN")
