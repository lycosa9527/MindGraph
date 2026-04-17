"""
CLI: check / deploy / reload MindGraph Fail2ban templates.

Run: python -m services.infrastructure.security.fail2ban_integration --help
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from services.infrastructure.security.fail2ban_integration.check import (
    Fail2banCheckResult,
    check_fail2ban_install,
    fail2ban_daemon_responding,
    is_linux,
    run_fail2ban_regex,
    run_fail2ban_reload,
)
from services.infrastructure.security.fail2ban_integration.constants import (
    ACTION_FILE,
    FILTER_FILE,
    JAIL_FILE,
    JAIL_NAME,
)
from services.infrastructure.security.fail2ban_integration.deploy import (
    deploy_fail2ban_templates,
)
from services.infrastructure.security.fail2ban_integration.patch_deployed import (
    npm_access_log_path,
    patch_action_mindgraph_root,
    patch_jail_logpath,
)
from services.infrastructure.security.fail2ban_integration.paths import (
    project_root_from_here,
)


def _print_result(result: Fail2banCheckResult) -> None:
    print(f"Platform Linux:        {result.linux}")
    print(f"fail2ban-client:       {result.fail2ban_client_on_path}")
    print(f"Daemon reachable:      {result.daemon_ok}")
    print(f"jail.d/{JAIL_FILE}:   {result.jail_config_present}")
    print(f"filter.d/{FILTER_FILE}: {result.filter_config_present}")
    print(f"action.d/{ACTION_FILE}: {result.action_config_present}")
    print(f"Jail '{JAIL_NAME}' loaded: {result.jail_listed}")
    if result.logpath:
        print(f"logpath:               {result.logpath}")
        print(f"logpath exists:        {result.logpath_exists}")
    else:
        print("logpath:               (not set or unreadable)")
    if result.jail_status_stdout and not result.jail_listed:
        print("--- fail2ban-client status output ---")
        print(result.jail_status_stdout)
    for msg in result.messages:
        print(f"Note: {msg}")
    print()
    if result.is_ok():
        print("Summary: OK — MindGraph Fail2ban jail looks configured.")
    else:
        print("Summary: action needed — see notes above or docs/FAIL2BAN_SETUP.md")


def cmd_check(etc_dir: Path) -> int:
    if not is_linux():
        print("This helper is for Linux hosts only.")
        return 2
    result = check_fail2ban_install(etc_dir)
    _print_result(result)
    return 0 if result.is_ok() else 1


def cmd_deploy(
    etc_dir: Path,
    mindgraph_root: Path,
    npm_home: Path | None,
    proxy_host: int,
    dry_run: bool,
) -> int:
    if not is_linux():
        print("This helper is for Linux hosts only.")
        return 2
    if dry_run:
        print("Dry run — no files written.")
    src_jail = mindgraph_root / "resources" / "fail2ban" / "jail.d" / JAIL_FILE
    if not src_jail.is_file():
        print(f"Missing repo templates under {mindgraph_root / 'resources' / 'fail2ban'}")
        return 2

    if dry_run:
        print(f"Would copy templates to {etc_dir}")
        logpath = npm_access_log_path(npm_home, proxy_host) if npm_home is not None else "(unchanged)"
        print(f"Would set MindGraph root: {mindgraph_root.resolve()}")
        print(f"Would set logpath: {logpath}")
        return 0

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        deploy_fail2ban_templates(etc_dir, mindgraph_root / "resources" / "fail2ban")
    except (OSError, FileNotFoundError) as exc:
        print(f"Deploy failed: {exc}")
        print("Try: sudo PYTHONPATH=<repo> python -m ... deploy")
        return 1

    action_path = etc_dir / "action.d" / ACTION_FILE
    jail_path = etc_dir / "jail.d" / JAIL_FILE
    patch_action_mindgraph_root(action_path, mindgraph_root)
    if npm_home is not None:
        patch_jail_logpath(jail_path, npm_access_log_path(npm_home, proxy_host))

    print(f"Installed templates under {etc_dir}")
    print("Edit /etc/fail2ban/abuseipdb.conf if you use AbuseIPDB reporting.")
    print("Then: sudo fail2ban-client reload")
    return 0


def cmd_reload() -> int:
    if not is_linux():
        print("This helper is for Linux hosts only.")
        return 2
    code, out = run_fail2ban_reload()
    if out:
        print(out)
    if code != 0:
        print("fail2ban-client reload failed (sudo may be required).")
        return 1
    print("fail2ban-client reload: OK")
    return 0


def cmd_validate(etc_dir: Path) -> int:
    if not is_linux():
        print("This helper is for Linux hosts only.")
        return 2
    result = check_fail2ban_install(etc_dir)
    logpath_s = result.logpath
    if not logpath_s:
        print("No logpath in jail config; run deploy first.")
        return 1
    lp = Path(logpath_s)
    filt = etc_dir / "filter.d" / FILTER_FILE
    if not lp.is_file():
        print(f"Log file missing: {lp}")
        return 1
    if not filt.is_file():
        print(f"Filter missing: {filt}")
        return 1
    ok, out = run_fail2ban_regex(lp, filt)
    print(out)
    return 0 if ok else 1


def cmd_setup(
    etc_dir: Path,
    mindgraph_root: Path,
    npm_home: Path | None,
    proxy_host: int,
    dry_run: bool,
) -> int:
    code = cmd_deploy(etc_dir, mindgraph_root, npm_home, proxy_host, dry_run)
    if code != 0 or dry_run:
        return code
    code = cmd_reload()
    if code != 0:
        return code
    return cmd_check(etc_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m services.infrastructure.security.fail2ban_integration",
        description="MindGraph Fail2ban: check, deploy templates, reload, validate.",
    )
    parser.add_argument(
        "--etc-dir",
        type=Path,
        default=Path("/etc/fail2ban"),
        help="Fail2ban config root (default: /etc/fail2ban)",
    )
    parser.add_argument(
        "--mindgraph-root",
        type=Path,
        default=None,
        help="MindGraph repository root (default: inferred from package location)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Print status of Fail2ban and the npm-mindgraph jail")

    deploy_p = sub.add_parser(
        "deploy",
        help="Copy templates to --etc-dir and patch MindGraph path (and logpath if set)",
    )
    deploy_p.add_argument(
        "--npm-home",
        type=Path,
        default=None,
        help="Nginx Proxy Manager install dir (e.g. /root/npm); sets proxy-host access logpath",
    )
    deploy_p.add_argument(
        "--proxy-host",
        type=int,
        default=1,
        help="proxy-host-<N> id in NPM (default: 1)",
    )
    deploy_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing files",
    )

    sub.add_parser("reload", help="Run fail2ban-client reload (sudo if not root)")

    sub.add_parser(
        "validate",
        help="Run fail2ban-regex against configured logpath and filter",
    )

    setup_p = sub.add_parser(
        "setup",
        help="deploy + reload + check (one step)",
    )
    setup_p.add_argument("--npm-home", type=Path, default=None)
    setup_p.add_argument("--proxy-host", type=int, default=1)
    setup_p.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    mindgraph_root = args.mindgraph_root or project_root_from_here()

    if args.command == "check":
        return cmd_check(args.etc_dir)

    if args.command == "deploy":
        return cmd_deploy(
            args.etc_dir,
            mindgraph_root,
            args.npm_home,
            args.proxy_host,
            args.dry_run,
        )

    if args.command == "reload":
        if not fail2ban_daemon_responding():
            print("fail2ban daemon not responding; fix before reload.")
            return 1
        return cmd_reload()

    if args.command == "validate":
        return cmd_validate(args.etc_dir)

    if args.command == "setup":
        return cmd_setup(
            args.etc_dir,
            mindgraph_root,
            args.npm_home,
            args.proxy_host,
            args.dry_run,
        )

    return 1
