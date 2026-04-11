"""Tests for Fail2ban helper (check + patch, no live fail2ban required)."""

from __future__ import annotations

from pathlib import Path

from services.infrastructure.security.fail2ban_integration.check import read_jail_logpath
from services.infrastructure.security.fail2ban_integration.patch_deployed import (
    npm_access_log_path,
    patch_action_mindgraph_root,
    patch_jail_logpath,
)


def test_read_jail_logpath(tmp_path: Path) -> None:
    jail = tmp_path / "jail.conf"
    jail.write_text(
        "[other]\nlogpath = /wrong\n\n[npm-mindgraph]\nlogpath = /data/logs/a.log\n",
        encoding="utf-8",
    )
    assert read_jail_logpath(jail) == "/data/logs/a.log"


def test_patch_jail_logpath(tmp_path: Path) -> None:
    jail = tmp_path / "jail.conf"
    jail.write_text(
        "[npm-mindgraph]\nenabled = true\nlogpath = /old/path.log\n",
        encoding="utf-8",
    )
    assert patch_jail_logpath(jail, "/new/path.log") is True
    text = jail.read_text(encoding="utf-8")
    assert "logpath = /new/path.log" in text
    assert patch_jail_logpath(jail, "/new/path.log") is False


def test_patch_action_mindgraph_root(tmp_path: Path) -> None:
    action = tmp_path / "action.conf"
    action.write_text(
        'actionban = cd "/CHANGE/ME/MindGraph" && python\n',
        encoding="utf-8",
    )
    root = tmp_path / "mg"
    root.mkdir()
    assert patch_action_mindgraph_root(action, root) is True
    out = action.read_text(encoding="utf-8")
    assert "/CHANGE/ME/MindGraph" not in out
    assert str(root.resolve()) in out


def test_npm_access_log_path(tmp_path: Path) -> None:
    npm = tmp_path / "npm"
    npm.mkdir()
    expected = str((npm / "data" / "logs" / "proxy-host-2_access.log").resolve())
    assert npm_access_log_path(npm, 2) == expected


def test_read_jail_logpath_missing(tmp_path: Path) -> None:
    assert read_jail_logpath(tmp_path / "nope.conf") is None
