"""Unit tests for MindMate Dify persona inputs and agent alias branding."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import HTTPException

from models.domain.auth import Organization
from routers.auth.admin.organization_mindmate_branding import apply_mindmate_branding_on_update
from services.dify.org_dify_inputs import apply_persona_inputs, persona_inputs_for_org

_AVATAR = "/static/org_mindmate_avatars/2/avatar.png"
_DIFY_URL = "https://dify.example.com/v1"


def _org(**fields: object) -> Organization:
    """Build a stand-in organization row."""
    defaults: dict[str, object] = {
        "name": "Org Name",
        "display_name": None,
        "mindmate_agent_name": None,
        "mindmate_agent_alias": None,
        "mindmate_agent_avatar_url": None,
        "dify_api_base_url": None,
        "dify_api_key": None,
    }
    defaults.update(fields)
    return cast(Organization, SimpleNamespace(**defaults))


def _privatized(**fields: object) -> Organization:
    """Organization that meets the privatization gate."""
    base: dict[str, object] = {
        "mindmate_agent_name": "八一思行者",
        "mindmate_agent_avatar_url": _AVATAR,
        "dify_api_base_url": _DIFY_URL,
        "dify_api_key": "key",
        "name": "八一",
        "display_name": "北京市八一学校附属玉泉中学",
    }
    base.update(fields)
    return _org(**base)


def test_missing_org_uses_public_labels() -> None:
    """No organization sends MindMate labels and an empty school name."""
    payload = persona_inputs_for_org(None)
    assert payload == {
        "mg_agent_name": "MindMate",
        "mg_agent_alias": "MindMate",
        "mg_school_name": "",
    }


def test_not_privatized_ignores_saved_name_and_alias() -> None:
    """A typed name is not sent until privatization is complete."""
    org = _org(
        mindmate_agent_name="远二启慧星",
        mindmate_agent_alias="远二小星",
        display_name="西安市莲湖区远东第二小学",
    )
    payload = persona_inputs_for_org(org)
    assert payload["mg_agent_name"] == "MindMate"
    assert payload["mg_agent_alias"] == "MindMate"
    assert payload["mg_school_name"] == "西安市莲湖区远东第二小学"
    assert tuple(payload) == ("mg_agent_name", "mg_agent_alias", "mg_school_name")


def test_privatized_uses_saved_name_and_alias() -> None:
    """Privatized schools send the saved agent name and alias."""
    payload = persona_inputs_for_org(_privatized(mindmate_agent_alias="小思"))
    assert payload["mg_agent_name"] == "八一思行者"
    assert payload["mg_agent_alias"] == "小思"
    assert payload["mg_school_name"] == "北京市八一学校附属玉泉中学"


def test_privatized_alias_falls_back_to_agent_name() -> None:
    """An empty alias uses the saved agent name."""
    payload = persona_inputs_for_org(_privatized(mindmate_agent_alias="  "))
    assert payload["mg_agent_alias"] == "八一思行者"


def test_school_name_falls_back_from_display_name_to_name() -> None:
    """School name prefers display_name, then the organization name."""
    named = persona_inputs_for_org(_org(display_name="  ", name="远东二小"))
    assert named["mg_school_name"] == "远东二小"
    displayed = persona_inputs_for_org(_org(display_name="展示名", name="远东二小"))
    assert displayed["mg_school_name"] == "展示名"


def test_apply_persona_inputs_overwrites_spoofed_keys() -> None:
    """Caller inputs cannot replace the three persona keys or add a blurb."""
    inputs: dict[str, object] = {
        "mg_agent_name": "spoof",
        "mg_agent_alias": "spoof",
        "mg_school_name": "spoof",
        "mg_school_blurb": "nope",
        "mg_dify_user": "user-1",
    }
    apply_persona_inputs(inputs, None)
    assert inputs["mg_agent_name"] == "MindMate"
    assert inputs["mg_agent_alias"] == "MindMate"
    assert inputs["mg_school_name"] == ""
    assert "mg_school_blurb" not in inputs
    assert inputs["mg_dify_user"] == "user-1"


def test_alias_over_ten_characters_is_rejected() -> None:
    """Alias uses the same 10-character cap as the agent name."""
    org = SimpleNamespace()
    with pytest.raises(HTTPException) as exc_info:
        apply_mindmate_branding_on_update(
            cast(Organization, org),
            {"mindmate_agent_alias": "12345678901"},
            "en",
        )
    assert exc_info.value.status_code == 400


def test_blank_alias_clears_saved_value() -> None:
    """Whitespace alias clears the column."""
    org = SimpleNamespace(mindmate_agent_alias="小思")
    apply_mindmate_branding_on_update(
        cast(Organization, org),
        {"mindmate_agent_alias": "   "},
        "en",
    )
    assert org.mindmate_agent_alias is None


def test_alias_is_stripped_on_save() -> None:
    """Saved alias drops surrounding whitespace."""
    org = SimpleNamespace()
    apply_mindmate_branding_on_update(
        cast(Organization, org),
        {"mindmate_agent_alias": " 小思 "},
        "en",
    )
    assert org.mindmate_agent_alias == "小思"
