"""Tests for stack COS planning helpers."""

from __future__ import annotations

from services.infrastructure.sync import stack_cos_plan


def _plan(*, reason: str = "up_to_date", update_needed: bool = False, cos_version: str = "1.0.0"):
    return {
        "update_needed": update_needed,
        "reason": reason,
        "cos_version": cos_version,
        "installed_version": "0.9.0",
    }


def test_stack_check_exit_code_up_to_date():
    assert (
        stack_cos_plan.stack_check_exit_code(
            _plan(update_needed=False),
            _plan(update_needed=False),
        )
        == 0
    )


def test_stack_check_exit_code_update_available():
    assert (
        stack_cos_plan.stack_check_exit_code(
            _plan(update_needed=True, cos_version="1.18.2"),
            _plan(update_needed=False),
        )
        == 1
    )


def test_stack_check_exit_code_not_configured():
    assert (
        stack_cos_plan.stack_check_exit_code(
            _plan(reason="cos_not_configured"),
            _plan(reason="cos_not_configured"),
        )
        == 2
    )


def test_stack_check_exit_code_both_meta_missing():
    assert (
        stack_cos_plan.stack_check_exit_code(
            _plan(reason="cos_meta_missing"),
            _plan(reason="cos_meta_missing"),
        )
        == 2
    )


def test_stack_check_exit_code_one_meta_missing_one_ok():
    assert (
        stack_cos_plan.stack_check_exit_code(
            _plan(reason="cos_meta_missing"),
            _plan(update_needed=False),
        )
        == 0
    )


def test_stack_update_prompt_partial():
    prompt = stack_cos_plan.stack_update_prompt(
        _plan(update_needed=True, cos_version="1.18.2"),
        _plan(reason="cos_meta_missing"),
    )
    assert prompt == "Install Qdrant 1.18.2 from COS now"


def test_resolve_stack_update_pending_only():
    plan = stack_cos_plan.resolve_stack_update(
        _plan(update_needed=True),
        _plan(update_needed=False),
        reinstall=False,
    )
    assert plan["qdrant"] == {"run": True, "force": False}
    assert plan["celery"] == {"run": False, "force": False}


def test_resolve_stack_update_reinstall():
    plan = stack_cos_plan.resolve_stack_update(
        _plan(update_needed=False),
        _plan(update_needed=False),
        reinstall=True,
    )
    assert plan["qdrant"] == {"run": True, "force": True}
    assert plan["celery"] == {"run": True, "force": True}


def test_verify_component_outcome_skips_missing_meta():
    assert stack_cos_plan.verify_component_outcome({"error": "cos_meta_missing"}) == "skipped"


def test_verify_component_outcome_verified():
    assert stack_cos_plan.verify_component_outcome({"ok": True, "verified": True}) == "verified"


def test_summarize_qdrant_needs_root():
    ok, code = stack_cos_plan.summarize_update_result("Qdrant", {"needs_root": True, "ok": False})
    assert ok is False
    assert code == 1


def test_summarize_qdrant_api_ok():
    ok, code = stack_cos_plan.summarize_update_result(
        "Qdrant",
        {"ok": True, "api_ok": True},
    )
    assert ok is True
    assert code == 0


def test_summarize_celery_import_ok():
    ok, code = stack_cos_plan.summarize_update_result(
        "Celery",
        {"ok": True, "import_ok": True},
    )
    assert ok is True
    assert code == 0
