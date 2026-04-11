"""
Optional Linux startup gate: exit if MindGraph Fail2ban templates are missing.

Controlled by FAIL2BAN_STARTUP_CHECK (default true on Linux). Set false in Docker
or hosts without Fail2ban.
"""

from __future__ import annotations

import logging
import os
import textwrap
from pathlib import Path
from typing import Optional

from services.infrastructure.security.fail2ban_integration.check import (
    check_fail2ban_install,
    is_linux,
)
from services.infrastructure.utils.launch_commands import (
    error_footer_launch_reference,
    lines_fail2ban_deploy,
)

logger = logging.getLogger(__name__)

_ENV_CHECK = "FAIL2BAN_STARTUP_CHECK"
_ENV_ETC = "FAIL2BAN_ETC"


def _banner_line() -> str:
    return "=" * 80


def _copy_paste_block() -> str:
    return "\n".join(lines_fail2ban_deploy())


def startup_fail2ban_check_enabled() -> bool:
    """True when we should enforce Fail2ban on this process (Linux only)."""
    if not is_linux():
        return False
    val = os.getenv(_ENV_CHECK, "true").strip().lower()
    return val not in ("0", "false", "no", "off", "disabled")


def evaluate_fail2ban_startup(etc_dir: Optional[Path] = None) -> Optional[str]:
    """
    Return None if startup may continue, or a short human-readable failure message.

    Does not exit the process.
    """
    if not startup_fail2ban_check_enabled():
        return None
    etc = etc_dir or Path(os.getenv(_ENV_ETC, "/etc/fail2ban"))
    result = check_fail2ban_install(etc)

    if not result.fail2ban_client_on_path:
        return textwrap.dedent(
            """
            Fail2ban is not installed or fail2ban-client is not on PATH.
            Install fail2ban on the host (e.g. apt install fail2ban), then deploy templates.
            """
        ).strip()

    if not result.daemon_ok:
        return textwrap.dedent(
            """
            Fail2ban is not running or fail2ban-client is not responding.
            Start the service (e.g. sudo systemctl enable --now fail2ban). Then deploy templates.
            """
        ).strip()

    if not (
        result.jail_config_present
        and result.filter_config_present
        and result.action_config_present
    ):
        return textwrap.dedent(
            """
            MindGraph Fail2ban templates are not deployed under /etc/fail2ban
            (missing jail.d, filter.d, or action.d files).
            """
        ).strip()

    if not result.jail_listed:
        return textwrap.dedent(
            """
            Fail2ban config files exist but the npm-mindgraph jail is not loaded.
            Fix config errors, then run: sudo fail2ban-client reload
            (see journalctl -u fail2ban -f).
            """
        ).strip()

    return None


def enforce_fail2ban_startup_or_exit(etc_dir: Optional[Path] = None) -> None:
    """Call os._exit(1) if Fail2ban checks fail when enabled."""
    message = evaluate_fail2ban_startup(etc_dir)
    if message is None:
        return

    banner = _banner_line()
    body = "\n".join(
        [
            banner,
            "FAIL2BAN: startup check failed — fix the issue below, then restart.",
            banner,
            "",
            message,
            "",
            "Run from the MindGraph repository root (copy-paste):",
            "",
            _copy_paste_block(),
            "",
            "See docs/FAIL2BAN_SETUP.md",
            *error_footer_launch_reference(),
            banner,
        ]
    )

    for line in body.splitlines():
        logger.error("[FAIL2BAN] %s", line)

    print()
    print(body)
    print()

    os._exit(1)  # pylint: disable=protected-access
