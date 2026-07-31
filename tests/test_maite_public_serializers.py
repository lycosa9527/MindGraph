"""Maite public serializers must never expose answer keys."""

from __future__ import annotations

from types import SimpleNamespace

from services.maite.domain.public_serializers import public_remedy_task, public_variant_task, strip_secret_fields


def test_strip_secret_fields_removes_backend_only_keys() -> None:
    """Strip reference answers and related secret keys from payloads."""
    cleaned = strip_secret_fields(
        {
            "summary": "ok",
            "reference_answer": "secret",
            "reference_strategy": "secret",
            "success_criteria": "secret",
            "expected_strategy": "secret",
        }
    )
    assert cleaned == {"summary": "ok"}


def test_public_variant_task_hides_expected_strategy() -> None:
    """Variant task serialization must hide expected_strategy and nested secrets."""
    task = SimpleNamespace(
        __table__=SimpleNamespace(
            columns=[
                SimpleNamespace(name="id"),
                SimpleNamespace(name="variant_text"),
                SimpleNamespace(name="expected_strategy"),
                SimpleNamespace(name="ai_feedback"),
            ]
        ),
        id=1,
        variant_text="x",
        expected_strategy="must-not-leak",
        ai_feedback={"reference_answer": "nope", "summary": "fine"},
    )
    public = public_variant_task(task)
    assert "expected_strategy" not in public
    assert public["ai_feedback"] == {"summary": "fine"}


def test_public_remedy_task_strips_payload_secrets() -> None:
    """Remedy task payload secrets must be stripped before client return."""
    task = SimpleNamespace(
        __table__=SimpleNamespace(
            columns=[
                SimpleNamespace(name="id"),
                SimpleNamespace(name="task_payload"),
            ]
        ),
        id=2,
        task_payload={"prompt": "q", "reference_answer": "a"},
    )
    public = public_remedy_task(task)
    assert public["task_payload"] == {"prompt": "q"}
