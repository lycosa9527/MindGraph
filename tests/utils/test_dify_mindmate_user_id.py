"""Tests for MindMate Dify user id mapping."""

import uuid

import pytest

from models.domain.auth import User
from utils import dify_mindmate_user_id as mod


def _user(phone: str, pk: int = 42) -> User:
    """User."""
    return User(
        id=pk,
        phone=phone,
        email=None,
        password_hash="x",
        name="t",
    )


def test_standard_mode_uses_prefixed_mg_user_pk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-UUID accounts always include the required deployment prefix."""
    monkeypatch.setattr(mod, "AUTH_MODE", "standard")
    monkeypatch.setenv("MINDMATE_DIFY_USER_PREFIX", "dev_roy")
    user = _user(str(uuid.uuid4()), pk=7)
    assert mod.mindmate_dify_user_id(user) == "dev_roy_mg_user_7"
    assert mod.mindmate_dify_user_aliases(user) == ["dev_roy_mg_user_7", "mg_user_7"]


def test_bayi_phone_login_uses_prefixed_mg_user_pk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phone login on /auth is not a vendor UUID, so Dify uses the install prefix."""
    monkeypatch.setattr(mod, "AUTH_MODE", "bayi")
    monkeypatch.setenv("MINDMATE_DIFY_USER_PREFIX", "dev_roy")
    user = _user("13800138000", pk=1)
    assert mod.mindmate_dify_user_id(user) == "dev_roy_mg_user_1"


def test_prefix_appends_legacy_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deployment prefix is the write id; the old mg_user key stays readable."""
    monkeypatch.setattr(mod, "AUTH_MODE", "standard")
    monkeypatch.setenv("MINDMATE_DIFY_USER_PREFIX", "Prod")
    user = _user("13800138000", pk=7)
    assert mod.mindmate_dify_user_id(user) == "prod_mg_user_7"
    assert mod.mindmate_dify_user_aliases(user) == ["prod_mg_user_7", "mg_user_7"]


def test_underscore_prefix_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """A prefix like dev_roy is part of the Dify user id."""
    monkeypatch.setattr(mod, "AUTH_MODE", "standard")
    monkeypatch.setenv("MINDMATE_DIFY_USER_PREFIX", "dev_roy")
    user = _user("13800138000", pk=7)
    assert mod.mindmate_dify_user_id(user) == "dev_roy_mg_user_7"
    assert mod.mindmate_dify_user_aliases(user) == ["dev_roy_mg_user_7", "mg_user_7"]


def test_missing_or_invalid_prefix_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank or punctuated prefix must not fall back to a shared mg_user id."""
    monkeypatch.setattr(mod, "AUTH_MODE", "standard")
    user = _user("13800138000", pk=7)
    monkeypatch.delenv("MINDMATE_DIFY_USER_PREFIX", raising=False)
    with pytest.raises(mod.MindmateDifyUserPrefixError):
        mod.mindmate_dify_user_id(user)
    monkeypatch.setenv("MINDMATE_DIFY_USER_PREFIX", "prod-west")
    with pytest.raises(mod.MindmateDifyUserPrefixError):
        mod.mindmate_dify_user_id(user)
    monkeypatch.setenv("MINDMATE_DIFY_USER_PREFIX", "dev_yourname")
    with pytest.raises(mod.MindmateDifyUserPrefixError):
        mod.mindmate_dify_user_id(user)


def test_bayi_sso_uuid_ignores_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vendor UUID identities are not rewritten when a deployment prefix is set."""
    monkeypatch.setattr(mod, "AUTH_MODE", "bayi")
    monkeypatch.setenv("MINDMATE_DIFY_USER_PREFIX", "prod")
    uid = uuid.uuid4()
    user = _user(str(uid))
    expected = str(uuid.UUID(str(uid)))
    assert mod.mindmate_dify_user_id(user) == expected
    assert mod.mindmate_dify_user_aliases(user) == [expected]


def test_bayi_sso_uuid_uses_canonical_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test bayi sso uuid uses canonical string."""
    monkeypatch.setattr(mod, "AUTH_MODE", "bayi")
    uid = uuid.uuid4()
    user = _user(str(uid))
    expected = str(uuid.UUID(str(uid)))
    assert mod.mindmate_dify_user_id(user) == expected
