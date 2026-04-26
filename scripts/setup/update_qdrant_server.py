#!/usr/bin/env python3
"""
Upgrade the Qdrant server binary installed via MindGraph setup (systemd + /usr/local/bin).

Resolves UserWarning from qdrant_client when the Python client is newer than the server
by replacing the binary with a release that matches your pinned qdrant-client (see
requirements.txt). Run on Linux as root, e.g.:

    sudo python3 scripts/setup/update_qdrant_server.py
    sudo python3 scripts/setup/update_qdrant_server.py --version 1.17.1
    python3 scripts/setup/update_qdrant_server.py --dry-run   # no root; prints URL only

Docker / remote Qdrant: upgrade the container image or server image to the same minor
line as qdrant-client instead of using this script.
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

QDRANT_LOCAL_BIN = "/usr/local/bin/qdrant"
QDRANT_SYSTEMD_PATH = "/etc/systemd/system/qdrant.service"
GITHUB_TARBALL_URL = "https://github.com/qdrant/qdrant/releases/download/v{version}/qdrant-{arch}.tar.gz"

# Official release tags are numeric semver (optional pre-release suffix).
_VERSION_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)*(?:-[0-9A-Za-z.-]+)?$")


def _parse_qdrant_version(raw: str) -> Optional[str]:
    """
    Normalize user input to a GitHub release tag fragment (no leading 'v').

    Accepts ``1.17.1`` or ``v1.17.1``. Rejects empty or unsafe strings.
    """
    cleaned = (raw or "").strip()
    if cleaned.lower().startswith("v") and len(cleaned) > 1:
        cleaned = cleaned[1:].strip()
    if not cleaned or not _VERSION_PATTERN.fullmatch(cleaned):
        return None
    return cleaned


def _linux_arch_suffix() -> Optional[str]:
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64-unknown-linux-gnu"
    if machine in ("aarch64", "arm64"):
        return "aarch64-unknown-linux-gnu"
    return None


def _download(url: str, dest: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            with open(dest, "wb") as outfile:
                shutil.copyfileobj(response, outfile)
        return True
    except (OSError, urllib.error.URLError, ValueError):
        return False


def _api_ok() -> bool:
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

    arch = _linux_arch_suffix()
    if arch is None:
        print(
            "[ERROR] Unsupported CPU; use an official Qdrant build from https://github.com/qdrant/qdrant/releases",
        )
        return 1

    url = GITHUB_TARBALL_URL.format(version=normalized, arch=arch)
    print(f"[INFO] Target Qdrant server version: v{normalized} ({arch})")
    print(f"[INFO] URL: {url}")

    if dry_run:
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

    tmp_dir = tempfile.mkdtemp(prefix="mg_qdrant_upgrade_")
    tar_path = os.path.join(tmp_dir, "qdrant.tgz")
    try:
        print("[INFO] Downloading tarball...")
        if not _download(url, tar_path):
            print("[ERROR] Download failed (check version exists on GitHub).")
            return 1

        print("[INFO] Extracting...")
        inner_bin = _extract_tarball(tar_path, tmp_dir)
        if not inner_bin:
            print("[ERROR] Archive did not contain a qdrant binary.")
            return 1

        had_systemd = os.path.isfile(QDRANT_SYSTEMD_PATH)
        if not had_systemd and _api_ok():
            print(
                "[WARNING] Something already responds on http://127.0.0.1:6333 but no "
                f"MindGraph systemd unit ({QDRANT_SYSTEMD_PATH}). Stop that Qdrant "
                "(Docker, manual binary, etc.) before replacing "
                f"{QDRANT_LOCAL_BIN} or you may corrupt storage.",
            )

        if had_systemd:
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
            if had_systemd:
                code, _out, err = _systemctl(["start", "qdrant"])
                if code != 0 and err:
                    print(f"[WARNING] systemctl start stderr: {err}")
            return 1

        print(f"[SUCCESS] Installed Qdrant -> {QDRANT_LOCAL_BIN}")

        if had_systemd:
            _systemctl(["daemon-reload"])
            print("[INFO] Starting qdrant service...")
            code, _out, err = _systemctl(["start", "qdrant"])
            if code != 0:
                print("[ERROR] systemctl start qdrant failed; check journalctl -u qdrant")
                if err:
                    print(f"[ERROR] systemctl stderr: {err}")
                return 1
        else:
            print(
                "[INFO] No systemd unit at /etc/systemd/system/qdrant.service; "
                "start Qdrant manually, then verify: "
                "curl -sf http://127.0.0.1:6333/collections >/dev/null",
            )
            return 0

        print("[INFO] Waiting for API on port 6333...")
        for _ in range(30):
            if _api_ok():
                print("[SUCCESS] Qdrant API is responding at http://127.0.0.1:6333")
                return 0
            time.sleep(1)

        print(
            "[ERROR] API did not respond in time; check: sudo journalctl -u qdrant -n 80",
        )
        return 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upgrade Qdrant server binary (MindGraph systemd install path).",
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
        help="Print target URL and exit without downloading.",
    )
    args = parser.parse_args()
    return run_upgrade(args.version, args.no_backup, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
