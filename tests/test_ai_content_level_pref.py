"""Tests for mind-map 专业程度 preference validation."""

import pytest
from pydantic import ValidationError

from models.requests.requests_auth import DiagramPreferencesUpdate
from services.utils.ai_content_level import is_valid_ai_content_level


def test_is_valid_ai_content_level_accepts_known_ids() -> None:
    """Allowlisted 专业程度 ids are accepted."""
    assert is_valid_ai_content_level("primary") is True
    assert is_valid_ai_content_level("expert") is True
    assert is_valid_ai_content_level("general") is True


def test_is_valid_ai_content_level_rejects_unknown() -> None:
    """Unknown or empty values are rejected."""
    assert is_valid_ai_content_level(None) is False
    assert is_valid_ai_content_level("") is False
    assert is_valid_ai_content_level("小学") is False
    assert is_valid_ai_content_level("unknown") is False


def test_diagram_preferences_accepts_ai_content_level_only() -> None:
    """Mind-map picker can PATCH 专业程度 without touching 学段."""
    body = DiagramPreferencesUpdate.model_validate({"ai_content_level": "university"})
    assert body.ai_content_level == "university"
    assert body.education_stage is None
    assert "education_stage" not in body.model_fields_set


def test_diagram_preferences_normalizes_ai_content_level_case() -> None:
    """Stored ids are lowercase."""
    body = DiagramPreferencesUpdate.model_validate({"ai_content_level": "Expert"})
    assert body.ai_content_level == "expert"


def test_diagram_preferences_rejects_invalid_ai_content_level() -> None:
    """Unknown 专业程度 ids fail validation."""
    with pytest.raises(ValidationError):
        DiagramPreferencesUpdate.model_validate({"ai_content_level": "小学"})


def test_diagram_preferences_still_accepts_education_stage() -> None:
    """Classic 学段 PATCH remains valid."""
    body = DiagramPreferencesUpdate.model_validate({"education_stage": "高中"})
    assert body.education_stage == "高中"
    assert "ai_content_level" not in body.model_fields_set


def test_diagram_preferences_accepts_v3_ribbon_fields() -> None:
    """V3 ribbon height and last tab can PATCH without 学段."""
    body = DiagramPreferencesUpdate.model_validate({"v3_ribbon_classic": True, "v3_ribbon_tab": "Design"})
    assert body.v3_ribbon_classic is True
    assert body.v3_ribbon_tab == "edit"
    assert "education_stage" not in body.model_fields_set


def test_diagram_preferences_rejects_unknown_v3_ribbon_tab() -> None:
    """Unknown ribbon tabs fail validation instead of being stored."""
    with pytest.raises(ValidationError):
        DiagramPreferencesUpdate.model_validate({"v3_ribbon_tab": "favorites"})
