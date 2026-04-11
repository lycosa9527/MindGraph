"""Tests for Fail2ban startup gate (evaluate only; no process exit)."""

from __future__ import annotations

from services.infrastructure.security.fail2ban_integration.check import Fail2banCheckResult
from services.infrastructure.security.fail2ban_integration import startup_gate as sg


def test_evaluate_skipped_when_not_linux(monkeypatch) -> None:
    monkeypatch.setattr(sg, "is_linux", lambda: False)
    assert sg.evaluate_fail2ban_startup() is None


def test_evaluate_skipped_when_env_disabled(monkeypatch) -> None:
    monkeypatch.setattr(sg, "is_linux", lambda: True)
    monkeypatch.setenv("FAIL2BAN_STARTUP_CHECK", "false")
    assert sg.evaluate_fail2ban_startup() is None


def test_evaluate_fails_missing_client(monkeypatch) -> None:
    monkeypatch.setattr(sg, "is_linux", lambda: True)
    monkeypatch.setenv("FAIL2BAN_STARTUP_CHECK", "true")

    def _fake(_path) -> Fail2banCheckResult:
        return Fail2banCheckResult(fail2ban_client_on_path=False)

    monkeypatch.setattr(sg, "check_fail2ban_install", _fake)
    msg = sg.evaluate_fail2ban_startup()
    assert msg is not None
    assert "fail2ban-client" in msg.lower() or "fail2ban" in msg.lower()


def test_evaluate_ok_when_all_green(monkeypatch) -> None:
    monkeypatch.setattr(sg, "is_linux", lambda: True)
    monkeypatch.setenv("FAIL2BAN_STARTUP_CHECK", "true")

    def _fake(_path) -> Fail2banCheckResult:
        return Fail2banCheckResult(
            fail2ban_client_on_path=True,
            daemon_ok=True,
            jail_config_present=True,
            filter_config_present=True,
            action_config_present=True,
            jail_listed=True,
        )

    monkeypatch.setattr(sg, "check_fail2ban_install", _fake)
    assert sg.evaluate_fail2ban_startup() is None


def test_startup_check_enabled_default_true_on_linux(monkeypatch) -> None:
    monkeypatch.setattr(sg, "is_linux", lambda: True)
    monkeypatch.delenv("FAIL2BAN_STARTUP_CHECK", raising=False)
    assert sg.startup_fail2ban_check_enabled() is True
