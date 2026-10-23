"""MindBot replies when the linked account is short of thinking coins."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.infrastructure.http.error_handler import ThinkingCoinInsufficientError
from services.mindbot.pipeline import thinking_coin_gate as gate_mod


@pytest.mark.asyncio
async def test_unlinked_sender_is_not_blocked() -> None:
    """A DingTalk sender with no platform account keeps the existing chat path."""
    reply = await gate_mod.mindbot_thinking_coin_block_reply(None, 4)
    assert reply is None


@pytest.mark.asyncio
async def test_short_balance_returns_localized_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """A linked account below the MindMate turn cost gets the catalog reply."""

    async def fake_user(_user_id: int) -> SimpleNamespace:
        return SimpleNamespace(ui_language="en")

    async def fake_assert(
        user_id: int,
        organization_id: int,
        request_type: str,
        lang: str = "en",
    ) -> bool:
        assert user_id == 7
        assert organization_id == 3
        assert request_type == "mindmate"
        assert lang == "en"
        raise ThinkingCoinInsufficientError(balance=1, cost=5, user_message="need coins")

    monkeypatch.setattr(gate_mod.user_cache, "get_by_id", fake_user)
    monkeypatch.setattr(gate_mod, "assert_thinking_coin_llm_budget", fake_assert)

    reply = await gate_mod.mindbot_thinking_coin_block_reply(7, 3)
    assert reply == "need coins"


@pytest.mark.asyncio
async def test_paid_account_is_not_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """School tiers that skip thinking coins still reach Dify."""

    async def fake_user(_user_id: int) -> SimpleNamespace:
        return SimpleNamespace(ui_language="zh")

    async def fake_assert(*_args: object, **_kwargs: object) -> bool:
        return False

    monkeypatch.setattr(gate_mod.user_cache, "get_by_id", fake_user)
    monkeypatch.setattr(gate_mod, "assert_thinking_coin_llm_budget", fake_assert)

    reply = await gate_mod.mindbot_thinking_coin_block_reply(7, 3)
    assert reply is None


@pytest.mark.asyncio
async def test_group_reply_omits_balance(monkeypatch: pytest.MonkeyPatch) -> None:
    """A group chat must not publish the sender's balance and cost."""

    async def fake_user(_user_id: int) -> SimpleNamespace:
        return SimpleNamespace(ui_language="zh", organization_id=9)

    async def fake_assert(*_args: object, **_kwargs: object) -> bool:
        raise ThinkingCoinInsufficientError(balance=1, cost=8, user_message="balance 1 need 8")

    monkeypatch.setattr(gate_mod.user_cache, "get_by_id", fake_user)
    monkeypatch.setattr(gate_mod, "assert_thinking_coin_llm_budget", fake_assert)

    reply = await gate_mod.mindbot_thinking_coin_block_reply(7, 3, reveal_balance=False)
    assert reply is not None
    assert "1" not in reply
    assert "8" not in reply
    assert "思维币不足" in reply


@pytest.mark.asyncio
async def test_wallet_outage_lets_the_turn_continue(monkeypatch: pytest.MonkeyPatch) -> None:
    """A database error during the check must not drop the DingTalk turn."""

    async def fake_user(_user_id: int) -> SimpleNamespace:
        return SimpleNamespace(ui_language="zh")

    async def fake_assert(*_args: object, **_kwargs: object) -> bool:
        raise ValueError("wallet unavailable")

    monkeypatch.setattr(gate_mod.user_cache, "get_by_id", fake_user)
    monkeypatch.setattr(gate_mod, "assert_thinking_coin_llm_budget", fake_assert)

    reply = await gate_mod.mindbot_thinking_coin_block_reply(7, 3)
    assert reply is None


@pytest.mark.asyncio
async def test_user_org_is_used_for_eligibility(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eligibility follows the linked account's school, not only the bot's org id."""
    seen: dict[str, int] = {}

    async def fake_user(_user_id: int) -> SimpleNamespace:
        return SimpleNamespace(ui_language="en", organization_id=9)

    async def fake_assert(
        _user_id: int,
        organization_id: int,
        _request_type: str,
        lang: str = "en",
    ) -> bool:
        seen["organization_id"] = organization_id
        seen["lang_is_en"] = 1 if lang == "en" else 0
        return True

    monkeypatch.setattr(gate_mod.user_cache, "get_by_id", fake_user)
    monkeypatch.setattr(gate_mod, "assert_thinking_coin_llm_budget", fake_assert)

    reply = await gate_mod.mindbot_thinking_coin_block_reply(7, 3)
    assert reply is None
    assert seen["organization_id"] == 9
    assert seen["lang_is_en"] == 1


def test_missing_ui_language_defaults_to_chinese() -> None:
    """DingTalk replies stay Chinese when the account has no saved UI language."""
    assert gate_mod.mindbot_reply_language(None) == "zh"
    assert gate_mod.mindbot_reply_language("  ") == "zh"
    assert gate_mod.mindbot_reply_language("en") == "en"
