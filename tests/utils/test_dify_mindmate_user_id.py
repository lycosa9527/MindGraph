"""Tests for MindMate Dify user id mapping."""

import uuid

import pytest

from models.domain.auth import User
from utils import dify_mindmate_user_id as mod


def _user(phone: str, pk: int = 42) -> User:
    return User(
        id=pk,
        phone=phone,
        email=None,
        password_hash="x",
        name="t",
    )


def test_standard_mode_uses_mg_user_pk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "AUTH_MODE", "standard")
    user = _user(str(uuid.uuid4()), pk=7)
    assert mod.mindmate_dify_user_id(user) == "mg_user_7"


def test_bayi_passkey_phone_non_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "AUTH_MODE", "bayi")
    user = _user("bayi@system.com", pk=1)
    assert mod.mindmate_dify_user_id(user) == "mg_user_1"


def test_bayi_sso_uuid_uses_canonical_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "AUTH_MODE", "bayi")
    uid = uuid.uuid4()
    user = _user(str(uid))
    expected = str(uuid.UUID(str(uid)))
    assert mod.mindmate_dify_user_id(user) == expected
