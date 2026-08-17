"""Resolve CELERY_WORKER_CONCURRENCY (default 4 prefork slots)."""

from __future__ import annotations

import pytest

from config.celery import celery_worker_concurrency


def test_celery_worker_concurrency_defaults_to_four(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset and blank env both yield four slots."""
    monkeypatch.delenv("CELERY_WORKER_CONCURRENCY", raising=False)
    assert celery_worker_concurrency() == 4
    monkeypatch.setenv("CELERY_WORKER_CONCURRENCY", "  ")
    assert celery_worker_concurrency() == 4


def test_celery_worker_concurrency_reads_positive_int(monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid override is honored."""
    monkeypatch.setenv("CELERY_WORKER_CONCURRENCY", "2")
    assert celery_worker_concurrency() == 2


def test_celery_worker_concurrency_rejects_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero, negative, and non-integers fall back to four; high values clamp."""
    monkeypatch.setenv("CELERY_WORKER_CONCURRENCY", "0")
    assert celery_worker_concurrency() == 4
    monkeypatch.setenv("CELERY_WORKER_CONCURRENCY", "-1")
    assert celery_worker_concurrency() == 4
    monkeypatch.setenv("CELERY_WORKER_CONCURRENCY", "abc")
    assert celery_worker_concurrency() == 4
    monkeypatch.setenv("CELERY_WORKER_CONCURRENCY", "99")
    assert celery_worker_concurrency() == 32
