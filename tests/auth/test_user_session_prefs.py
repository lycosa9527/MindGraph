"""Session preference payload used by login / register /me."""

import pytest
from pydantic import ValidationError

from models.domain.auth import User
from models.requests.requests_auth import DiagramPreferencesUpdate, LanguagePreferencesUpdate
from routers.auth.user_session_prefs import (
    coerce_overseas_ui_language_prefs,
    language_preference_patch_fields,
    user_preference_fields,
)


def test_user_preference_fields_include_ui_version_and_languages() -> None:
    """Login JSON must carry every persisted personalization column."""
    user = User(id=7, password_hash="x")
    user.ui_language = "zh"
    user.prompt_language = "zh"
    user.ui_version = "chinese"
    user.match_prompt_to_ui = False
    user.bilingual_ui_enabled = True
    user.presenter_ui_locale = "en"
    user.allows_simplified_chinese = True
    user.education_stage = "高中"
    user.ai_content_level = "university"
    user.v3_ribbon_classic = True
    user.v3_ribbon_tab = "design"
    payload = user_preference_fields(user)
    assert payload["ui_language"] == "zh"
    assert payload["prompt_language"] == "zh"
    assert payload["ui_version"] == "chinese"
    assert payload["match_prompt_to_ui"] is False
    assert payload["bilingual_ui_enabled"] is True
    assert payload["presenter_ui_locale"] == "en"
    assert payload["allows_simplified_chinese"] is True
    assert payload["education_stage"] == "高中"
    assert payload["ai_content_level"] == "university"
    assert payload["v3_ribbon_classic"] is True
    assert payload["v3_ribbon_tab"] == "design"


def test_user_preference_fields_defaults_when_unset() -> None:
    """Unset optional prefs stay None; boolean flags keep model defaults."""
    user = User(id=1, password_hash="x")
    payload = user_preference_fields(user)
    assert payload["ui_language"] is None
    assert payload["prompt_language"] is None
    assert payload["match_prompt_to_ui"] is True
    assert payload["bilingual_ui_enabled"] is False
    assert payload["presenter_ui_locale"] is None
    assert payload["allows_simplified_chinese"] is True
    assert "ui_version" in payload
    assert "education_stage" in payload
    assert "ai_content_level" in payload
    assert payload["v3_ribbon_classic"] is False
    assert payload["v3_ribbon_tab"] is None


def test_language_preference_patch_fields_are_the_settings_subset() -> None:
    """PATCH response omits diagram prefs and keeps language columns."""
    user = User(id=7, password_hash="x")
    user.ui_language = "zh"
    user.prompt_language = "zh"
    user.ui_version = "chinese"
    user.match_prompt_to_ui = False
    user.bilingual_ui_enabled = True
    user.presenter_ui_locale = "ja"
    user.education_stage = "高中"
    payload = language_preference_patch_fields(user)
    assert set(payload) == {
        "ui_language",
        "prompt_language",
        "ui_version",
        "match_prompt_to_ui",
        "bilingual_ui_enabled",
        "presenter_ui_locale",
    }
    assert payload["ui_language"] == "zh"
    assert payload["ui_version"] == "chinese"
    assert payload["bilingual_ui_enabled"] is True
    assert payload["presenter_ui_locale"] == "ja"


def test_coerce_overseas_rewrites_zh_presenter_locale() -> None:
    """Overseas policy must rewrite presenter zh the same as UI language."""
    user = User(id=3, password_hash="x")
    user.allows_simplified_chinese = False
    user.ui_language = "zh"
    user.prompt_language = "zh"
    user.presenter_ui_locale = "zh"
    assert coerce_overseas_ui_language_prefs(user) is True
    assert user.ui_language == "en"
    assert user.prompt_language == "en"
    assert user.presenter_ui_locale == "en"


def test_language_preferences_accepts_bilingual_fields() -> None:
    """PATCH body accepts bilingual chrome prefs with a UI locale presenter."""
    body = LanguagePreferencesUpdate.model_validate(
        {"bilingual_ui_enabled": True, "presenter_ui_locale": "JA"}
    )
    assert body.bilingual_ui_enabled is True
    assert body.presenter_ui_locale == "ja"


def test_language_preferences_rejects_unknown_presenter_locale() -> None:
    """Unknown presenter locales fail validation instead of being stored."""
    with pytest.raises(ValidationError):
        LanguagePreferencesUpdate.model_validate({"presenter_ui_locale": "zzz"})


def test_diagram_preferences_accepts_v3_ribbon_fields() -> None:
    """V3 ribbon height and last tab can PATCH without 学段."""
    body = DiagramPreferencesUpdate.model_validate({"v3_ribbon_classic": True, "v3_ribbon_tab": "Design"})
    assert body.v3_ribbon_classic is True
    assert body.v3_ribbon_tab == "edit"
    assert "education_stage" not in body.model_fields_set
    draw = DiagramPreferencesUpdate.model_validate({"v3_ribbon_tab": "draw"})
    assert draw.v3_ribbon_tab == "edit"
    learn = DiagramPreferencesUpdate.model_validate({"v3_ribbon_tab": "learn"})
    assert learn.v3_ribbon_tab == "teaching"
    ai = DiagramPreferencesUpdate.model_validate({"v3_ribbon_tab": "ai"})
    assert ai.v3_ribbon_tab == "ai"


def test_diagram_preferences_rejects_unknown_v3_ribbon_tab() -> None:
    """Unknown ribbon tabs fail validation instead of being stored."""
    with pytest.raises(ValidationError):
        DiagramPreferencesUpdate.model_validate({"v3_ribbon_tab": "favorites"})
