#!/usr/bin/env python3
"""
Install or upgrade Qdrant and Celery from Tencent COS (interactive).

When COS ``meta.json`` for each artifact reports a newer version than locally
installed, choose **Update both** to pull from COS (Qdrant requires root).

COS layout (under ``COS_SYNC_KEY_PREFIX``, else ``COS_KEY_PREFIX``)::

    sync/qdrant/meta.json
    sync/qdrant/v{version}/qdrant-{arch}.tar.gz
    sync/celery/meta.json
    sync/celery/v{version}/celery-{version}-py3-none-any.whl
    sync/crowdsec/blocklist.txt
    sync/abuseipdb/blocklist.txt
    sync/geolite/GeoLite2-Country.mmdb

Usage (repo root, WSL + conda python313)::

  conda activate python313
  python scripts/db/update_stack_from_cos.py

Do **not** use bare ``sudo python3`` — that is system Python without ``cos-python-sdk-v5``.
Menu 1/3/4/5 need no sudo. For Qdrant install (menu 2), use conda Python as root::

  sudo -E "$(which python)" scripts/db/update_stack_from_cos.py

Loads ``.env`` from the project root automatically (or ``MINDGRAPH_ENV_FILE``).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Callable, List, Tuple

try:
    from _path_setup import project_root
except ModuleNotFoundError:
    from scripts.db._path_setup import project_root

from services.infrastructure.sync.celery_cos_sync import (
    celery_cos_update_needed,
    get_celery_cos_status,
    publish_celery_to_cos_manual,
    publish_celery_wheel_file,
    read_celery_cos_meta,
    update_celery_from_cos,
    verify_celery_cos_pull,
)
from services.infrastructure.sync.celery_update_state import read_celery_update_state
from services.infrastructure.sync.qdrant_cos_sync import (
    get_qdrant_cos_status,
    publish_qdrant_tarball_file,
    publish_qdrant_to_cos_manual,
    qdrant_cos_update_needed,
    read_qdrant_cos_meta,
    update_qdrant_from_cos,
    verify_qdrant_cos_pull,
)
from services.infrastructure.sync.qdrant_update_state import read_qdrant_update_state
from services.infrastructure.sync.stack_cos_plan import (
    StackUpdatePlan,
    artifact_on_cos,
    resolve_stack_update,
    stack_check_exit_code,
    stack_has_pending_updates,
    stack_update_prompt,
    summarize_update_result,
    verify_component_outcome,
)
from services.utils import tencent_cos_client

MINDGRAPH_ROOT = project_root


def _cos_sdk_help() -> str:
    return (
        "cos-python-sdk-v5 is not installed for this Python interpreter.\n"
        f"  Current: {sys.executable}\n"
        "  Fix: conda activate python313, then run without bare sudo python3:\n"
        "    python scripts/db/update_stack_from_cos.py\n"
        "  Qdrant install only (needs root) — keep conda Python:\n"
        '    sudo -E "$(which python)" scripts/db/update_stack_from_cos.py'
    )


def _cos_sdk_ready() -> bool:
    if tencent_cos_client.cos_sdk_available():
        return True
    print("[ERROR] COS SDK missing", file=sys.stderr)
    print(_cos_sdk_help(), file=sys.stderr)
    return False


def _print_cos_env_summary() -> None:
    conn = tencent_cos_client.test_cos_connection()
    env_path = project_root / ".env"
    print(f"MindGraph root: {MINDGRAPH_ROOT}")
    print(f"Python:         {sys.executable}")
    print(f"Env file:       {env_path if env_path.is_file() else '(not found — set COS vars in environment)'}")
    if not conn.get("configured"):
        print("[WARN] COS not configured — set TENCENT_SMS_SECRET_* and COS_BUCKET in .env", file=sys.stderr)
        return
    if conn.get("ok"):
        print(f"COS:            bucket={conn.get('bucket')} prefix={conn.get('key_prefix')}")
        return
    error = conn.get("error")
    if error == "cos_sdk_missing":
        print("[WARN] COS configured in .env but SDK missing for this Python", file=sys.stderr)
        print(_cos_sdk_help(), file=sys.stderr)
        return
    print(f"[WARN] COS configured but connection failed: {error}", file=sys.stderr)


UpdatePlanFetcher = Callable[[], dict]


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _prompt_yes_no(question: str, default_yes: bool) -> bool:
    hint = "Y/n" if default_yes else "y/N"
    raw = input(f"{question} [{hint}]: ").strip().lower()
    if not raw:
        return default_yes
    return raw in ("y", "yes")


def _prompt_menu_choice() -> str:
    print()
    print("Stack COS (Qdrant + Celery)")
    print("  1) Check both (COS vs installed)")
    print("  2) Update both from COS")
    print("  3) Status (full JSON)")
    print("  4) Publish to COS (publisher)")
    print("  5) Verify COS downloads (SHA-256)")
    print("  q) Quit")
    return input("Choose [1]: ").strip().lower() or "1"


def _describe_plan(label: str, plan: dict) -> None:
    installed = plan.get("installed_version") or "(not installed)"
    cos_version = plan.get("cos_version") or "(missing on COS)"
    print(f"[{label}]")
    print(f"  Installed: {installed}")
    print(f"  COS:       {cos_version}")
    reason = plan.get("reason")
    if reason == "cos_not_configured":
        print("  Result:    COS credentials not configured")
    elif reason == "cos_sdk_missing":
        print("  Result:    COS SDK missing for this Python (use conda python313)")
    elif reason == "cos_meta_missing":
        print("  Result:    COS meta.json not found")
    elif plan.get("update_needed"):
        print("  Result:    update available (COS is newer)")
    else:
        print("  Result:    up to date")


async def _fetch_plan(fetcher: UpdatePlanFetcher) -> dict:
    if not tencent_cos_client.cos_credentials_configured():
        return {"update_needed": False, "reason": "cos_not_configured"}
    if not tencent_cos_client.cos_sdk_available():
        return {"update_needed": False, "reason": "cos_sdk_missing"}
    return await asyncio.to_thread(fetcher)


async def _fetch_both_plans() -> Tuple[dict, dict]:
    qdrant_plan, celery_plan = await asyncio.gather(
        _fetch_plan(qdrant_cos_update_needed),
        _fetch_plan(celery_cos_update_needed),
    )
    return qdrant_plan, celery_plan


async def _action_check() -> int:
    if not _cos_sdk_ready():
        return 2
    qdrant_plan, celery_plan = await _fetch_both_plans()
    if qdrant_plan.get("reason") == "cos_not_configured":
        print("[ERROR] COS credentials not configured in .env", file=sys.stderr)
        return 2
    if qdrant_plan.get("reason") == "cos_sdk_missing" or celery_plan.get("reason") == "cos_sdk_missing":
        return 2
    print("[CHECK]")
    _describe_plan("Qdrant", qdrant_plan)
    print()
    _describe_plan("Celery", celery_plan)
    return stack_check_exit_code(qdrant_plan, celery_plan)


async def _run_stack_updates(update_plan: StackUpdatePlan) -> int:
    exit_code = 0
    if update_plan["qdrant"]["run"]:
        print("[UPDATE] Qdrant")
        qdrant_result = await update_qdrant_from_cos(force=update_plan["qdrant"]["force"])
        _print_json(qdrant_result)
        ok, code = summarize_update_result("Qdrant", qdrant_result)
        if qdrant_result.get("needs_root"):
            print("[ERROR] Run with sudo for systemd install", file=sys.stderr)
        elif ok:
            print("[SUCCESS] Qdrant update complete")
        else:
            print("[ERROR] Qdrant update failed", file=sys.stderr)
        exit_code = max(exit_code, code)

    if update_plan["celery"]["run"]:
        print("[UPDATE] Celery")
        celery_result = await update_celery_from_cos(force=update_plan["celery"]["force"])
        _print_json(celery_result)
        ok, code = summarize_update_result("Celery", celery_result)
        if ok:
            print("[SUCCESS] Celery update complete — restart MindGraph/Celery worker if running")
        else:
            print("[ERROR] Celery update failed", file=sys.stderr)
        exit_code = max(exit_code, code)

    return exit_code


async def _action_update() -> int:
    if not _cos_sdk_ready():
        return 1
    qdrant_plan, celery_plan = await _fetch_both_plans()
    if qdrant_plan.get("reason") == "cos_not_configured":
        print("[ERROR] COS credentials not configured in .env", file=sys.stderr)
        return 1

    print("[UPDATE]")
    _describe_plan("Qdrant", qdrant_plan)
    print()
    _describe_plan("Celery", celery_plan)
    print()

    if not artifact_on_cos(qdrant_plan) and not artifact_on_cos(celery_plan):
        print("[ERROR] Neither Qdrant nor Celery meta.json found on COS", file=sys.stderr)
        return 1

    pending = stack_has_pending_updates(qdrant_plan, celery_plan)
    reinstall = False
    if pending:
        prompt = stack_update_prompt(qdrant_plan, celery_plan)
        if prompt and not _prompt_yes_no(prompt, default_yes=True):
            print("Cancelled.")
            return 0
    elif not _prompt_yes_no(
        "No pending updates. Reinstall components that exist on COS anyway",
        default_yes=False,
    ):
        print("Cancelled.")
        return 0
    else:
        reinstall = True

    update_plan = resolve_stack_update(qdrant_plan, celery_plan, reinstall=reinstall)
    if not update_plan["qdrant"]["run"] and not update_plan["celery"]["run"]:
        print("[INFO] Nothing to update.")
        return 0
    return await _run_stack_updates(update_plan)


async def _action_status() -> int:
    qdrant_status, celery_status = await asyncio.gather(
        get_qdrant_cos_status(),
        get_celery_cos_status(),
    )
    qdrant_plan, celery_plan = await _fetch_both_plans()
    payload = {
        "cos_connection": tencent_cos_client.test_cos_connection(),
        "qdrant": {
            **qdrant_status,
            "update_state": read_qdrant_update_state(),
            "update_plan": qdrant_plan,
        },
        "celery": {
            **celery_status,
            "update_state": read_celery_update_state(),
            "update_plan": celery_plan,
        },
        "stack_check_exit_code": stack_check_exit_code(qdrant_plan, celery_plan),
    }
    _print_json(payload)
    return 0


def _prompt_publish_targets() -> List[str]:
    print("Publish target:")
    print("  1) Both")
    print("  2) Qdrant only")
    print("  3) Celery only")
    choice = input("Choose [1]: ").strip().lower() or "1"
    if choice in ("2", "q", "qdrant"):
        return ["qdrant"]
    if choice in ("3", "c", "celery"):
        return ["celery"]
    return ["qdrant", "celery"]


def _validate_publish_file(path_text: str, label: str) -> Path | None:
    path = Path(path_text).expanduser()
    if not path.is_file():
        print(f"[ERROR] {label} file not found: {path}", file=sys.stderr)
        return None
    return path


async def _publish_qdrant() -> int:
    source = input("Qdrant source github or file [github]: ").strip().lower() or "github"
    from_file: Path | None = None
    if source.startswith("f"):
        path_text = input("Path to qdrant-*.tar.gz: ").strip()
        if not path_text:
            print("Cancelled.")
            return 0
        from_file = _validate_publish_file(path_text, "Qdrant")
        if from_file is None:
            return 1

    force = False
    cos_meta = await asyncio.to_thread(read_qdrant_cos_meta)
    if cos_meta and cos_meta.get("version"):
        print(f"Qdrant COS already has v{cos_meta['version']}.")
        if not _prompt_yes_no("Re-upload Qdrant anyway", default_yes=False):
            print("Skipped Qdrant publish.")
            return 0
        force = True

    if from_file is not None:
        result = await publish_qdrant_tarball_file(from_file, force=force)
    else:
        result = await publish_qdrant_to_cos_manual(force=force)
    _print_json(result)
    return 0 if result.get("ok") else 1


async def _publish_celery() -> int:
    source = input("Celery source pypi or file [pypi]: ").strip().lower() or "pypi"
    from_file: Path | None = None
    if source.startswith("f"):
        path_text = input("Path to celery-*.whl or *.zip (zip must contain a .whl): ").strip()
        if not path_text:
            print("Cancelled.")
            return 0
        from_file = _validate_publish_file(path_text, "Celery")
        if from_file is None:
            return 1

    force = False
    cos_meta = await asyncio.to_thread(read_celery_cos_meta)
    if cos_meta and cos_meta.get("version"):
        print(f"Celery COS already has v{cos_meta['version']}.")
        if not _prompt_yes_no("Re-upload Celery anyway", default_yes=False):
            print("Skipped Celery publish.")
            return 0
        force = True

    if from_file is not None:
        result = await publish_celery_wheel_file(from_file, force=force)
    else:
        result = await publish_celery_to_cos_manual(force=force)
    _print_json(result)
    return 0 if result.get("ok") else 1


async def _action_publish() -> int:
    if not _cos_sdk_ready():
        return 1
    conn = tencent_cos_client.test_cos_connection()
    if not conn.get("ok"):
        print(f"[ERROR] COS connection failed: {conn.get('error')}", file=sys.stderr)
        return 1
    print(f"[INFO] COS bucket={conn.get('bucket')} prefix={conn.get('key_prefix')}")

    targets = _prompt_publish_targets()
    exit_code = 0
    if "qdrant" in targets:
        exit_code = max(exit_code, await _publish_qdrant())
    if "celery" in targets:
        exit_code = max(exit_code, await _publish_celery())
    return exit_code


async def _action_verify_pull() -> int:
    if not _cos_sdk_ready():
        return 1
    qdrant_result, celery_result = await asyncio.gather(
        verify_qdrant_cos_pull(),
        verify_celery_cos_pull(),
    )
    print("[Qdrant]")
    _print_json(qdrant_result)
    print("[Celery]")
    _print_json(celery_result)

    exit_code = 0
    for label, result in (("Qdrant", qdrant_result), ("Celery", celery_result)):
        outcome = verify_component_outcome(result)
        if outcome == "verified":
            print(f"[SUCCESS] {label} COS pull verified (SHA-256 match)")
        elif outcome == "skipped":
            print(f"[SKIP] {label} not on COS (meta.json missing)")
        else:
            print(f"[ERROR] {label} COS pull verification failed", file=sys.stderr)
            exit_code = 1
    return exit_code


async def _interactive_main() -> int:
    _print_cos_env_summary()
    while True:
        choice = _prompt_menu_choice()
        if choice in ("q", "quit", "exit"):
            return 0
        if choice == "1":
            code = await _action_check()
            if code == 2:
                return 2
            continue
        if choice == "2":
            return await _action_update()
        if choice == "3":
            await _action_status()
            continue
        if choice == "4":
            code = await _action_publish()
            if code != 0:
                return code
            continue
        if choice == "5":
            code = await _action_verify_pull()
            if code != 0:
                return code
            continue
        print("Invalid choice. Enter 1–5 or q.")


def main() -> int:
    """Interactive Qdrant + Celery COS check / update menu."""
    return asyncio.run(_interactive_main())


if __name__ == "__main__":
    raise SystemExit(main())
