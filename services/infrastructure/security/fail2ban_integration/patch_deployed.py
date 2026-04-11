"""
Patch deployed Fail2ban files under /etc/fail2ban (paths and MindGraph root).
"""

from __future__ import annotations

import re
from pathlib import Path

from services.infrastructure.security.fail2ban_integration.constants import (
    JAIL_NAME,
    PLACEHOLDER_MINDGRAPH_ROOT,
)


def npm_access_log_path(npm_home: Path, proxy_host_id: int) -> str:
    """Nginx Proxy Manager combined access log path on the host."""
    resolved = npm_home.expanduser().resolve()
    return str(resolved / "data" / "logs" / f"proxy-host-{proxy_host_id}_access.log")


def patch_action_mindgraph_root(action_file: Path, mindgraph_root: Path) -> bool:
    """
    Replace PLACEHOLDER_MINDGRAPH_ROOT with the real repo path in actionban line.

    Returns True if the file was modified.
    """
    text = action_file.read_text(encoding="utf-8")
    root_s = str(mindgraph_root.expanduser().resolve())
    if PLACEHOLDER_MINDGRAPH_ROOT not in text and root_s in text:
        return False
    new_text = text.replace(PLACEHOLDER_MINDGRAPH_ROOT, root_s)
    if new_text == text:
        return False
    action_file.write_text(new_text, encoding="utf-8")
    return True


def patch_jail_logpath(jail_file: Path, logpath: str) -> bool:
    """
    Set logpath = ... in the [npm-mindgraph] section.

    Returns True if the file was modified.
    """
    text = jail_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    in_section = False
    changed = False
    logpath_re = re.compile(r"^(\s*logpath\s*=\s*)(\S+)(\s*)$")

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped == f"[{JAIL_NAME}]"
            continue
        if in_section:
            raw = line.rstrip("\r\n")
            match = logpath_re.match(raw)
            if match:
                ending = "\r\n" if line.endswith("\r\n") else "\n"
                new_line = f"{match.group(1)}{logpath}{match.group(3)}{ending}"
                if lines[idx] != new_line:
                    lines[idx] = new_line
                    changed = True
                break

    if changed:
        jail_file.write_text("".join(lines), encoding="utf-8")
    return changed
