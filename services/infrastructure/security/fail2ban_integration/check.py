"""
Diagnostics for Fail2ban + MindGraph jail (no root required for most checks).
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from services.infrastructure.security.fail2ban_integration.constants import (
    ACTION_FILE,
    FILTER_FILE,
    JAIL_FILE,
    JAIL_NAME,
)


@dataclass
class Fail2banCheckResult:
    """Outcome of a full check run."""

    linux: bool = True
    fail2ban_client_on_path: bool = False
    daemon_ok: bool = False
    jail_config_present: bool = False
    filter_config_present: bool = False
    action_config_present: bool = False
    jail_listed: bool = False
    jail_status_stdout: str = ""
    logpath: Optional[str] = None
    logpath_exists: bool = False
    messages: List[str] = field(default_factory=list)

    def ok(self) -> bool:
        """True when the MindGraph jail is installed and the daemon sees it."""
        return (
            self.linux
            and self.fail2ban_client_on_path
            and self.daemon_ok
            and self.jail_config_present
            and self.jail_listed
            and self.logpath is not None
            and self.logpath_exists
        )


def _run(
    args: List[str],
    timeout: float = 20.0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def is_linux() -> bool:
    return platform.system().lower() == "linux"


def fail2ban_client_available() -> bool:
    return shutil.which("fail2ban-client") is not None


def fail2ban_daemon_responding() -> bool:
    if not fail2ban_client_available():
        return False
    result = _run(["fail2ban-client", "status"])
    return result.returncode == 0


def read_jail_logpath(jail_file: Path) -> Optional[str]:
    """Return logpath value from [npm-mindgraph] in jail config."""
    if not jail_file.is_file():
        return None
    text = jail_file.read_text(encoding="utf-8")
    in_section = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("["):
            in_section = line == f"[{JAIL_NAME}]"
            continue
        if not in_section:
            continue
        if line.lower().startswith("logpath"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None


def jail_known_to_fail2ban() -> tuple[bool, str]:
    """True if fail2ban-client status npm-mindgraph succeeds."""
    result = _run(["fail2ban-client", "status", JAIL_NAME])
    out = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, out.strip()


def run_fail2ban_regex(logpath: Path, filter_path: Path) -> tuple[bool, str]:
    """Run fail2ban-regex if available. Returns (success, combined output)."""
    regex_tool = shutil.which("fail2ban-regex")
    if not regex_tool:
        return False, "fail2ban-regex not on PATH"
    result = _run(
        [
            "fail2ban-regex",
            str(logpath),
            str(filter_path),
        ],
        timeout=120.0,
    )
    out = (result.stdout or "") + "\n" + (result.stderr or "")
    return result.returncode == 0, out.strip()


def check_fail2ban_install(
    etc_fail2ban: Path = Path("/etc/fail2ban"),
) -> Fail2banCheckResult:
    """
    Inspect Fail2ban and MindGraph jail files on this host.

    Does not mutate system state. Safe without root for file existence checks.
    """
    result = Fail2banCheckResult()
    result.linux = is_linux()
    if not result.linux:
        result.messages.append("Fail2ban helper targets Linux hosts only.")
        return result

    result.fail2ban_client_on_path = fail2ban_client_available()
    if not result.fail2ban_client_on_path:
        result.messages.append("Install fail2ban (e.g. apt install fail2ban).")
        return result

    result.daemon_ok = fail2ban_daemon_responding()
    if not result.daemon_ok:
        result.messages.append(
            "fail2ban-client status failed; start the service "
            "(e.g. sudo systemctl enable --now fail2ban).",
        )

    jail_path = etc_fail2ban / "jail.d" / JAIL_FILE
    filter_path = etc_fail2ban / "filter.d" / FILTER_FILE
    action_path = etc_fail2ban / "action.d" / ACTION_FILE

    result.jail_config_present = jail_path.is_file()
    result.filter_config_present = filter_path.is_file()
    result.action_config_present = action_path.is_file()

    if not result.jail_config_present:
        result.messages.append(
            f"Missing {jail_path}; deploy templates from resources/fail2ban/.",
        )

    result.logpath = read_jail_logpath(jail_path) if result.jail_config_present else None
    if result.logpath:
        lp = Path(result.logpath)
        result.logpath_exists = lp.is_file()
        if not result.logpath_exists:
            result.messages.append(
                f"logpath does not exist yet: {result.logpath} "
                "(set NPM paths or create the proxy host in Nginx Proxy Manager).",
            )

    if result.daemon_ok:
        listed, status_out = jail_known_to_fail2ban()
        result.jail_listed = listed
        result.jail_status_stdout = status_out
        if not listed and result.jail_config_present:
            result.messages.append(
                f"Jail [{JAIL_NAME}] not loaded; run: sudo fail2ban-client reload "
                "and fix any errors in journalctl -u fail2ban.",
            )

    return result


def sudo_prefix() -> List[str]:
    """Prefix for commands that need root when not already root."""
    if not is_linux():
        return []
    proc = subprocess.run(
        ["id", "-u"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if proc.returncode != 0:
        return ["sudo"]
    try:
        uid = int((proc.stdout or "").strip())
    except ValueError:
        return ["sudo"]
    if uid == 0:
        return []
    return ["sudo"]


def run_fail2ban_reload() -> tuple[int, str]:
    """Reload fail2ban (uses sudo when not root)."""
    cmd = sudo_prefix() + ["fail2ban-client", "reload"]
    proc = _run(cmd, timeout=60.0)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()
