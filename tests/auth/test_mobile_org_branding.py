"""Phone branding payload and ownership checks."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routers.auth.admin.organization_mobile_branding import (
    assert_mobile_created_org,
    parse_mobile_branding_body,
)
from utils.auth.admin_scope import build_admin_scope


class _User:
    """Minimal actor for AdminScope."""

    def __init__(self, role: str, user_id: int):
        """Store the role and id the scope builder reads."""
        self.role = role
        self.id = user_id
        self.organization_id = None
        self.phone = None


def test_parse_mobile_branding_keeps_public_fields() -> None:
    """Agent name, alias, and display name are trimmed. A null avatar clears it."""
    parsed = parse_mobile_branding_body(
        {
            "mindmate_agent_name": " 小思 ",
            "mindmate_agent_alias": " 思 ",
            "display_name": " 北京市第一中学 ",
            "mindmate_agent_avatar_url": None,
        },
        "zh",
    )
    assert parsed == {
        "mindmate_agent_name": "小思",
        "mindmate_agent_alias": "思",
        "display_name": "北京市第一中学",
        "mindmate_agent_avatar_url": None,
    }


def test_parse_mobile_branding_rejects_secrets_and_avatar_urls() -> None:
    """The phone body cannot set Dify keys, the internal name, or an avatar path."""
    with pytest.raises(HTTPException) as secret_exc:
        parse_mobile_branding_body({"display_name": "A", "dify_api_key": "sk-secret"}, "en")
    assert secret_exc.value.status_code == 400

    with pytest.raises(HTTPException) as name_exc:
        parse_mobile_branding_body({"name": "Renamed School"}, "en")
    assert name_exc.value.status_code == 400

    with pytest.raises(HTTPException) as avatar_exc:
        parse_mobile_branding_body(
            {"mindmate_agent_avatar_url": "/static/org_mindmate_avatars/1/avatar.png"},
            "en",
        )
    assert avatar_exc.value.status_code == 400


def test_parse_mobile_branding_rejects_overlong_names() -> None:
    """Agent name stays at 10 characters. Display name stays at 200."""
    with pytest.raises(HTTPException) as agent_exc:
        parse_mobile_branding_body({"mindmate_agent_name": "一二三四五六七八九十多"}, "zh")
    assert agent_exc.value.status_code == 400

    with pytest.raises(HTTPException) as alias_exc:
        parse_mobile_branding_body({"mindmate_agent_alias": "x" * 11}, "en")
    assert alias_exc.value.status_code == 400

    with pytest.raises(HTTPException) as display_exc:
        parse_mobile_branding_body({"display_name": "校" * 201}, "zh")
    assert display_exc.value.status_code == 400


def _org(org_id: int, invited_by: int | None) -> SimpleNamespace:
    """Organization stand-in with only the fields the guard reads."""
    return SimpleNamespace(id=org_id, invited_by_user_id=invited_by)


def test_mobile_branding_owner_guard() -> None:
    """Superadmin edits any school. A creator edits their school. Others get 404."""
    superadmin = build_admin_scope(_User("superadmin", 1), lang="en")
    assert_mobile_created_org(superadmin, _org(9, None), "en")

    expert = build_admin_scope(_User("expert", 5), lang="en", invited_org_ids=frozenset({10}))
    assert_mobile_created_org(expert, _org(10, 5), "en")

    with pytest.raises(HTTPException) as foreign_exc:
        assert_mobile_created_org(expert, _org(99, 8), "en")
    assert foreign_exc.value.status_code == 404

    with pytest.raises(HTTPException) as legacy_exc:
        assert_mobile_created_org(expert, _org(3, None), "en")
    assert legacy_exc.value.status_code == 404

    researcher = build_admin_scope(_User("platform_bd", 9), lang="en", invited_org_ids=frozenset({10}))
    assert_mobile_created_org(researcher, _org(10, 9), "en")
    with pytest.raises(HTTPException) as researcher_exc:
        assert_mobile_created_org(researcher, _org(10, 5), "en")
    assert researcher_exc.value.status_code == 404
