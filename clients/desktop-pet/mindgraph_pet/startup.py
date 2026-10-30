"""Open the pet when the user logs in."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_RUN_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"


def set_open_at_login(enabled: bool, executable: Path) -> str:
    """Register or clear the login item. Returns an error string, or empty on success."""
    if sys.platform == "win32":
        return _windows(enabled, executable)
    if sys.platform == "darwin":
        return _mac(enabled, executable)
    return ""


def _windows(enabled: bool, executable: Path) -> str:
    if enabled:
        command = ["reg", "add", _RUN_KEY, "/v", "MindGraph Pet", "/t", "REG_SZ", "/d", str(executable), "/f"]
    else:
        command = ["reg", "delete", _RUN_KEY, "/v", "MindGraph Pet", "/f"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        return (completed.stderr or completed.stdout or "login item failed").strip()
    return ""


def _mac(enabled: bool, executable: Path) -> str:
    app = executable
    if app.suffix != ".app":
        for parent in executable.parents:
            if parent.suffix == ".app":
                app = parent
                break
    if enabled:
        script = (
            f'tell application "System Events" to make login item at end with properties {{path:"{app}", hidden:false}}'
        )
    else:
        script = 'tell application "System Events" to delete login item "MindGraph Pet"'
    completed = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        return (completed.stderr or completed.stdout or "login item failed").strip()
    return ""
