"""Tests for unified stack COS CLI."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from scripts.db import update_stack_from_cos as cli


def test_prompt_yes_no_default_yes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert cli._prompt_yes_no("Proceed", default_yes=True) is True


def test_prompt_yes_no_default_no(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert cli._prompt_yes_no("Proceed", default_yes=False) is False


@pytest.mark.asyncio
async def test_action_update_cancelled_when_up_to_date(monkeypatch):
    plans = (
        {
            "update_needed": False,
            "reason": "up_to_date",
            "cos_version": "5.6.3",
            "installed_version": "5.6.3",
        },
        {
            "update_needed": False,
            "reason": "up_to_date",
            "cos_version": "1.18.2",
            "installed_version": "1.18.2",
        },
    )
    monkeypatch.setattr(cli, "_fetch_both_plans", AsyncMock(return_value=plans))
    monkeypatch.setattr(cli, "_prompt_yes_no", lambda question, default_yes: False)
    code = await cli._action_update()
    assert code == 0


@pytest.mark.asyncio
async def test_action_update_runs_pending(monkeypatch):
    plans = (
        {
            "update_needed": True,
            "reason": "cos_newer",
            "cos_version": "1.18.2",
            "installed_version": "1.18.1",
        },
        {
            "update_needed": False,
            "reason": "up_to_date",
            "cos_version": "5.6.3",
            "installed_version": "5.6.3",
        },
    )
    monkeypatch.setattr(cli, "_fetch_both_plans", AsyncMock(return_value=plans))
    monkeypatch.setattr(cli, "_prompt_yes_no", lambda question, default_yes: True)
    run_updates = AsyncMock(return_value=0)
    monkeypatch.setattr(cli, "_run_stack_updates", run_updates)
    code = await cli._action_update()
    assert code == 0
    run_updates.assert_awaited_once()
    assert run_updates.await_args is not None
    plan = run_updates.await_args.args[0]
    assert plan["qdrant"]["run"] is True
    assert plan["celery"]["run"] is False
