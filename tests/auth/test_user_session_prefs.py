"""Session preference payload used by login / register /me."""

import pytest
from pydantic import ValidationError

from models.domain.auth import User
from models.requests.requests_auth import DiagramPreferencesUpdate
from routers.auth.user_session_prefs import language_preference_patch_fields, user_preference_fields


def test_user_preference_fields_include_ui_version_and_languages() -> None:
    """Login JSON must carry every persisted personalization column."""
    user = User(id=7, password_hash="x")
    user.ui_language = "zh"
    user.prompt_language = "zh"
    user.ui_version = "chinese"
    user.match_prompt_to_ui = False
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
    user.education_stage = "高中"
    payload = language_preference_patch_fields(user)
    assert set(payload) == {
        "ui_language",
        "prompt_language",
        "ui_version",
        "match_prompt_to_ui",
    }
    assert payload["ui_language"] == "zh"
    assert payload["ui_version"] == "chinese"


def test_diagram_preferences_accepts_v3_ribbon_fields() -> None:
    """V3 ribbon height and last tab can PATCH without 学段."""
    body = DiagramPreferencesUpdate.model_validate({"v3_ribbon_classic": True, "v3_ribbon_tab": "Design"})
    assert body.v3_ribbon_classic is True
    assert body.v3_ribbon_tab == "design"
    assert "education_stage" not in body.model_fields_set


def test_diagram_preferences_rejects_unknown_v3_ribbon_tab() -> None:
    """Unknown ribbon tabs fail validation instead of being stored."""
    with pytest.raises(ValidationError):
        DiagramPreferencesUpdate.model_validate({"v3_ribbon_tab": "favorites"})
