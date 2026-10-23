"""Overseas accounts never generate Simplified Chinese unless the env switch is on."""

import json
from types import SimpleNamespace

import pytest

from services.infrastructure.utils.log_user_context import bind_log_user, reset_log_user
from services.mind_classroom.prompts.mastery_prompts import build_axis_contract_block
from utils.chinese_language_policy import (
    coerce_generation_language,
    effective_language_for_thinking_user,
    guard_json_text,
    guard_user_visible,
    simplified_chinese_forbidden,
    to_traditional_chinese,
    user_allows_simplified_chinese,
)
from utils.prompt_locale import append_traditional_output_rule, output_language_instruction


def _overseas() -> SimpleNamespace:
    return SimpleNamespace(id=7, name="Overseas", allows_simplified_chinese=False)


def test_explicit_zh_becomes_traditional_registry_code() -> None:
    """Simplified and Traditional tags both resolve to the registry code zh-hant."""
    user = _overseas()
    assert effective_language_for_thinking_user(user, "zh") == "zh-hant"
    assert effective_language_for_thinking_user(user, "zh-tw") == "zh-hant"


def test_simplified_glyphs_switch_generation_to_traditional() -> None:
    """Simplified-only characters force Traditional generation."""
    user = _overseas()
    assert effective_language_for_thinking_user(user, "en", "中国") == "zh-hant"


def test_shared_hanzi_without_simplified_forms_keeps_requested_language() -> None:
    """Characters that are identical in both scripts do not change the language."""
    user = _overseas()
    assert effective_language_for_thinking_user(user, "en", "人") == "en"


def test_mainland_account_keeps_simplified() -> None:
    """Accounts that allow Simplified Chinese keep the requested code."""
    user = SimpleNamespace(id=1, name="Mainland", allows_simplified_chinese=True)
    assert effective_language_for_thinking_user(user, "zh", "中国") == "zh"


def test_env_switch_restores_simplified_chinese_for_overseas_accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    """OVERSEAS_SIMPLIFIED_CHINESE=true leaves the account mark and allows zh."""
    user = _overseas()
    monkeypatch.setattr(
        "utils.chinese_language_policy.overseas_simplified_chinese_enabled",
        lambda: True,
    )
    assert user_allows_simplified_chinese(user) is True
    assert effective_language_for_thinking_user(user, "zh", "中国") == "zh"
    token = bind_log_user(user)
    try:
        assert simplified_chinese_forbidden() is False
        assert "简体中文" in output_language_instruction("zh")
    finally:
        reset_log_user(token)


def test_bound_account_rewrites_prompt_footer_and_returned_text() -> None:
    """A bound overseas account gets a Traditional prompt footer and Traditional text."""
    token = bind_log_user(_overseas())
    try:
        assert simplified_chinese_forbidden() is True
        footer = output_language_instruction("zh")
        assert "繁體中文" in footer
        assert "简体中文" not in footer
        assert coerce_generation_language("zh", "苹果") == "zh-hant"
        assert to_traditional_chinese("中国") == "中國"
        assert guard_user_visible({"text": "中国", "ok": True}) == {"text": "中國", "ok": True}
        raw = json.dumps({"caption": "中国"}, ensure_ascii=False)
        assert json.loads(guard_json_text(raw))["caption"] == "中國"
        assert "繁體中文" in append_traditional_output_rule("写一段说明。")
    finally:
        reset_log_user(token)
    assert simplified_chinese_forbidden() is False
    assert append_traditional_output_rule("写一段说明。") == "写一段说明。"


def test_classroom_contract_asks_for_traditional_only_for_zh_hant() -> None:
    """Lecture jobs stored as zh-hant tell the model to write Traditional Chinese."""
    traditional = build_axis_contract_block({"language": "zh-hant", "diagram_type": "mindmap"})
    simplified = build_axis_contract_block({"language": "zh", "diagram_type": "mindmap"})
    assert "繁體中文" in traditional
    assert "繁體中文" not in simplified
