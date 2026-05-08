#!/usr/bin/env python3
"""
Install or upgrade Qdrant for MindGraph.

Runs interactively: you choose **full install** (binary + config + systemd + API check)
or **update only** (replace binary + restart; keeps existing config).

Non-interactive (pipe / CI): set ``MINDGRAPH_NON_INTERACTIVE=1`` — always performs full install.

Examples::

    sudo python3 scripts/setup/update_qdrant_server.py
    sudo python3 scripts/setup/update_qdrant_server.py --version 1.17.1
    python3 scripts/setup/update_qdrant_server.py --dry-run

Conda: ``sudo $(which python3) scripts/setup/update_qdrant_server.py``

Docker / remote Qdrant: upgrade the server image to match ``qdrant-client`` in
requirements.txt instead of this script.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from typing import Optional, Tuple

# Keep in sync with QDRANT_GITHUB_VERSION in scripts/setup/setup.py
DEFAULT_QDRANT_VERSION = "1.17.1"

MODE_FULL = "full"
MODE_UPDATE_ONLY = "update_only"

QDRANT_LOCAL_BIN = "/usr/local/bin/qdrant"
QDRANT_CONFIG_PATH = "/etc/qdrant/config.yaml"
QDRANT_SYSTEMD_PATH = "/etc/systemd/system/qdrant.service"
# Keep QDRANT_CONFIG_YAML and QDRANT_SYSTEMD_UNIT in sync with scripts/setup/setup.py
QDRANT_CONFIG_YAML = """storage:
  storage_path: "/var/lib/qdrant/storage"
  snapshots_path: "/var/lib/qdrant/snapshots"
service:
  host: "0.0.0.0"
  api_port: 6333
  grpc_port: 6334
log_level: INFO
"""
QDRANT_SYSTEMD_UNIT = """[Unit]
Description=Qdrant Vector Database
Documentation=https://qdrant.tech/documentation/
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/qdrant --config-path /etc/qdrant/config.yaml
Restart=always
RestartSec=5
User=root
WorkingDirectory=/var/lib/qdrant
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
GITHUB_TARBALL_URL = "https://github.com/qdrant/qdrant/releases/download/v{version}/qdrant-{arch}.tar.gz"

_VERSION_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)*(?:-[0-9A-Za-z.-]+)?$")


def _stdin_is_tty() -> bool:
    """True if stdin is an interactive terminal."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _non_interactive_env() -> bool:
    """MINDGRAPH_NON_INTERACTIVE=1 skips prompts (same convention as scripts/setup/setup.py)."""
    value = os.environ.get("MINDGRAPH_NON_INTERACTIVE", "").strip().lower()
    return value in ("1", "true", "yes")


def prompt_yes_no(message: str, default: bool = False) -> bool:
    """Ask yes/no; empty input uses default."""
    tag = "Y/n" if default else "y/N"
    try:
        line = input(f"{message} [{tag}]: ").strip().lower()
    except EOFError:
        return default
    if not line:
        return default
    return line in ("y", "yes", "1", "true")


def resolve_qdrant_mode() -> str:
    """
    Ask full install vs update-only when interactive.

    Returns:
        MODE_FULL or MODE_UPDATE_ONLY
    """
    if not _stdin_is_tty() or _non_interactive_env():
        print(
            "[INFO] Non-interactive (pipe or MINDGRAPH_NON_INTERACTIVE=1): "
            "full MindGraph Qdrant setup.",
        )
        return MODE_FULL

    print("\n--- Qdrant setup ---")
    print("  1) Full install — GitHub binary, config + systemd if needed, verify API")
    print(
        "  2) Update only — replace binary and restart service (keeps config; "
        "requires existing qdrant.service)",
    )
    while True:
        try:
            line = input("Choose 1 or 2 [1]: ").strip()
        except EOFError:
            return MODE_FULL
        if not line or line == "1":
            return MODE_FULL
        if line == "2":
            return MODE_UPDATE_ONLY
        print("    Enter 1 or 2.")


def resolve_config_overwrite(mode: str) -> bool:
    """Ask whether to replace existing MindGraph config (full install only)."""
    if mode != MODE_FULL:
        return False
    if not _stdin_is_tty() or _non_interactive_env():
        return False
    if not os.path.isfile(QDRANT_CONFIG_PATH):
        return False
    return prompt_yes_no(
        f"Replace existing {QDRANT_CONFIG_PATH} with MindGraph default template?",
        default=False,
    )


def _parse_qdrant_version(raw: str) -> Optional[str]:
    """Normalize GitHub release tag fragment (no leading ``v``)."""
    cleaned = (raw or "").strip()
    if cleaned.lower().startswith("v") and len(cleaned) > 1:
        cleaned = cleaned[1:].strip()
    if not cleaned or not _VERSION_PATTERN.fullmatch(cleaned):
        return None
    return cleaned


def _linux_qdrant_tarball_urls(version: str) -> list[str]:
    """GitHub tarball URLs for this machine."""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "x86_64-unknown-linux-gnu"
        return [GITHUB_TARBALL_URL.format(version=version, arch=arch)]
    if machine in ("aarch64", "arm64"):
        gnu = "aarch64-unknown-linux-gnu"
        musl = "aarch64-unknown-linux-musl"
        return [
            GITHUB_TARBALL_URL.format(version=version, arch=gnu),
            GITHUB_TARBALL_URL.format(version=version, arch=musl),
        ]
    return []


def _download(url: str, dest: str) -> bool:
    """Fetch ``url`` to ``dest``; return True on success."""
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "MindGraph-qdrant-setup/1 "
                    "(https://github.com/lycosa9527/MindGraph)"
                ),
            },
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            with open(dest, "wb") as outfile:
                shutil.copyfileobj(response, outfile)
        return True
    except (OSError, urllib.error.URLError, ValueError):
        return False


def _api_ok() -> bool:
    """True when local Qdrant REST API returns HTTP 200 on /collections."""
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:6333/collections",
            timeout=5,
        ) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


def _systemctl(args: list[str]) -> Tuple[int, str, str]:
    completed = subprocess.run(
        ["systemctl", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _wait_for_qdrant_api(seconds: int = 30) -> bool:
    """Poll ``/collections`` until success or ``seconds`` elapsed."""
    for _ in range(seconds):
        if _api_ok():
            return True
        time.sleep(1)
    return False


def deploy_qdrant_systemd_stack(*, overwrite_config: bool = False) -> bool:
    """
    Ensure dirs, MindGraph config, systemd unit, enable + restart.

    Caller must be root. Preserves existing config unless ``overwrite_config``.
    """
    if not shutil.which("systemctl"):
        print(
            "[ERROR] systemctl not in PATH — enable systemd (e.g. WSL2 /etc/wsl.conf). "
            "See docs/QDRANT_SETUP.md",
        )
        return False
    try:
        os.makedirs("/var/lib/qdrant/storage", mode=0o755, exist_ok=True)
        os.makedirs("/var/lib/qdrant/snapshots", mode=0o755, exist_ok=True)
        os.makedirs(os.path.dirname(QDRANT_CONFIG_PATH), mode=0o755, exist_ok=True)
        existed_cfg = os.path.isfile(QDRANT_CONFIG_PATH)
        if overwrite_config or not existed_cfg:
            with open(QDRANT_CONFIG_PATH, "w", encoding="utf-8") as handle:
                handle.write(QDRANT_CONFIG_YAML)
            verb = "Overwrote" if overwrite_config and existed_cfg else "Wrote"
            print(f"[INFO] {verb} MindGraph Qdrant config -> {QDRANT_CONFIG_PATH}")
        else:
            print(f"[INFO] Keeping existing config -> {QDRANT_CONFIG_PATH}")
        with open(QDRANT_SYSTEMD_PATH, "w", encoding="utf-8") as handle:
            handle.write(QDRANT_SYSTEMD_UNIT)
        print(f"[INFO] Installed systemd unit -> {QDRANT_SYSTEMD_PATH}")
    except OSError as exc:
        print(f"[ERROR] Could not write Qdrant config or systemd unit: {exc}")
        return False

    code, _, err = _systemctl(["daemon-reload"])
    if code != 0:
        print(f"[WARNING] systemctl daemon-reload exited {code}: {err}")

    code, _, err = _systemctl(["enable", "qdrant"])
    if code != 0:
        print(f"[WARNING] systemctl enable qdrant exited {code}: {err}")

    print("[INFO] Restarting qdrant service...")
    code, _, err = _systemctl(["restart", "qdrant"])
    if code != 0:
        code_start, _, err_start = _systemctl(["start", "qdrant"])
        if code_start != 0:
            print(f"[ERROR] systemctl restart/start qdrant failed: {err or err_start}")
            print("[INFO] Check: sudo journalctl -u qdrant -n 80")
            return False
    return True


def finish_and_verify_qdrant() -> int:
    print("[INFO] Waiting for API on port 6333...")
    if _wait_for_qdrant_api():
        print("[SUCCESS] Qdrant API is responding at http://127.0.0.1:6333")
        print("[INFO] Set QDRANT_HOST=localhost:6333 in .env for Knowledge Space (see env.example)")
        return 0
    print("[ERROR] API did not respond in time; check: sudo journalctl -u qdrant -n 80")
    return 1


def _extract_tarball(tar_path: str, dest_dir: str) -> Optional[str]:
    try:
        with tarfile.open(tar_path, "r:gz") as archive:
            if sys.version_info >= (3, 12):
                archive.extractall(dest_dir, filter="data")
            else:
                archive.extractall(dest_dir)
    except (OSError, tarfile.TarError):
        return None
    inner_bin = os.path.join(dest_dir, "qdrant")
    if os.path.isfile(inner_bin):
        return inner_bin
    return None


def _install_binary(source: str, dest: str, backup: bool) -> bool:
    if os.path.isfile(dest) and backup:
        backup_path = f"{dest}.bak"
        try:
            shutil.copy2(dest, backup_path)
            print(f"[INFO] Backed up existing binary -> {backup_path}")
        except OSError as exc:
            print(f"[ERROR] Could not back up {dest}: {exc}")
            return False
    try:
        shutil.copy2(source, dest)
        os.chmod(dest, 0o755)
    except OSError as exc:
        print(f"[ERROR] Could not install binary to {dest}: {exc}")
        return False
    return True


def _systemctl_restart_qdrant(label: str) -> bool:
    """Run daemon-reload, then restart qdrant (fall back to start)."""
    _systemctl(["daemon-reload"])
    print(f"[INFO] {label}")
    code, _, err = _systemctl(["restart", "qdrant"])
    if code != 0:
        code, _, err = _systemctl(["start", "qdrant"])
    if code != 0:
        print("[ERROR] systemctl restart/start qdrant failed; check journalctl -u qdrant")
        if err:
            print(f"[ERROR] systemctl stderr: {err}")
        return False
    return True


def run_upgrade(version: str, no_backup: bool, dry_run: bool) -> int:
    if platform.system().lower() != "linux":
        print("[ERROR] This script only supports Linux (GitHub prebuilt binary).")
        return 1

    normalized = _parse_qdrant_version(version)
    if not normalized:
        print(
            "[ERROR] Invalid --version; use a release tag like 1.17.1 or v1.17.1 "
            "(see https://github.com/qdrant/qdrant/releases).",
        )
        return 1

    urls = _linux_qdrant_tarball_urls(normalized)
    if not urls:
        print(
            "[ERROR] Unsupported CPU; use an official Qdrant build from https://github.com/qdrant/qdrant/releases",
        )
        return 1

    print(f"[INFO] Target Qdrant server version: v{normalized}")
    for idx, candidate in enumerate(urls):
        label = "primary" if idx == 0 else "fallback"
        print(f"[INFO] Tarball candidate ({label}): {candidate}")

    if dry_run:
        print("[INFO] Dry run: would download binary to /usr/local/bin/qdrant.")
        print(
            "[INFO] Dry run: interactive run would ask full install vs update-only "
            "(non-interactive defaults to full).",
        )
        print("[INFO] Dry run: not downloading or installing.")
        return 0

    try:
        if os.geteuid() != 0:
            print("[ERROR] Run as root so the binary can be installed under /usr/local/bin.")
            print("        Example: sudo python3 scripts/setup/update_qdrant_server.py")
            return 1
    except AttributeError:
        print("[ERROR] This script requires a Unix-like system with geteuid().")
        return 1

    mode = resolve_qdrant_mode()
    overwrite_cfg = resolve_config_overwrite(mode)

    if not shutil.which("systemctl"):
        print(
            "[ERROR] systemd (systemctl) is required. Enable it on WSL2 or see docs/QDRANT_SETUP.md",
        )
        return 1

    if mode == MODE_UPDATE_ONLY and not os.path.isfile(QDRANT_SYSTEMD_PATH):
        print(
            "[ERROR] Update-only requires an existing MindGraph/system qdrant.service. "
            "Re-run and choose option 1 (full install).",
        )
        return 1

    tmp_dir = tempfile.mkdtemp(prefix="mg_qdrant_upgrade_")
    tar_path = os.path.join(tmp_dir, "qdrant.tgz")
    try:
        downloaded = False
        for candidate_url in urls:
            print(f"[INFO] Downloading tarball...\n    {candidate_url}")
            if os.path.isfile(tar_path):
                try:
                    os.unlink(tar_path)
                except OSError:
                    pass
            if _download(candidate_url, tar_path):
                downloaded = True
                break
            print("[WARNING] Download failed; trying next candidate if available...")
        if not downloaded:
            print("[ERROR] Download failed for all URLs (check version exists on GitHub).")
            return 1

        print("[INFO] Extracting...")
        inner_bin = _extract_tarball(tar_path, tmp_dir)
        if not inner_bin:
            print("[ERROR] Archive did not contain a qdrant binary.")
            return 1

        had_unit = os.path.isfile(QDRANT_SYSTEMD_PATH)
        if not had_unit and _api_ok():
            print(
                "[WARNING] Something already responds on http://127.0.0.1:6333 but no "
                f"MindGraph systemd unit ({QDRANT_SYSTEMD_PATH}). Stop that Qdrant "
                "(Docker, manual binary, etc.) before replacing "
                f"{QDRANT_LOCAL_BIN} or you may corrupt storage.",
            )

        if had_unit:
            print("[INFO] Stopping qdrant service...")
            code, _out, err = _systemctl(["stop", "qdrant"])
            if code != 0:
                print(
                    "[WARNING] systemctl stop qdrant exited with "
                    f"{code}; stop Qdrant manually if the service is still running.",
                )
                if err:
                    print(f"[WARNING] systemctl stderr: {err}")
            time.sleep(2)

        if not _install_binary(inner_bin, QDRANT_LOCAL_BIN, backup=not no_backup):
            if had_unit:
                code, _out, err = _systemctl(["start", "qdrant"])
                if code != 0 and err:
                    print(f"[WARNING] systemctl start stderr: {err}")
            return 1

        print(f"[SUCCESS] Installed Qdrant -> {QDRANT_LOCAL_BIN}")

        if mode == MODE_UPDATE_ONLY:
            if not _systemctl_restart_qdrant("Restarting qdrant service (update-only)..."):
                return 1
            return finish_and_verify_qdrant()

        if had_unit and overwrite_cfg:
            try:
                with open(QDRANT_CONFIG_PATH, "w", encoding="utf-8") as handle:
                    handle.write(QDRANT_CONFIG_YAML)
                print(f"[INFO] Overwrote MindGraph Qdrant config -> {QDRANT_CONFIG_PATH}")
            except OSError as exc:
                print(f"[ERROR] Could not overwrite config: {exc}")
                return 1

        if had_unit:
            if not _systemctl_restart_qdrant("Restarting qdrant service (existing unit)..."):
                return 1
        else:
            print("[INFO] Deploying MindGraph Qdrant systemd stack...")
            if not deploy_qdrant_systemd_stack(overwrite_config=overwrite_cfg):
                return 1

        return finish_and_verify_qdrant()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MindGraph Qdrant: interactive full install or binary update.",
        epilog=(
            "Interactive: choose full install vs update-only. "
            "Non-interactive: export MINDGRAPH_NON_INTERACTIVE=1 for full install without prompts."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_QDRANT_VERSION,
        help=f"Qdrant release tag without v prefix (default: {DEFAULT_QDRANT_VERSION})",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help=f"Do not save {QDRANT_LOCAL_BIN}.bak before replacing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print tarball URLs only; does not install or prompt.",
    )
    args = parser.parse_args()
    return run_upgrade(args.version, args.no_backup, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
