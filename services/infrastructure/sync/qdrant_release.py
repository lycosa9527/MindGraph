"""
Qdrant server release helpers (version, arch, install).

Shared by setup.py and COS mirror sync.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

QDRANT_GITHUB_VERSION = "1.18.1"
QDRANT_LOCAL_BIN = "/usr/local/bin/qdrant"
QDRANT_CONFIG_PATH = "/etc/qdrant/config.yaml"
QDRANT_SYSTEMD_PATH = "/etc/systemd/system/qdrant.service"
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
Description=Qdrant vector search engine
Documentation=https://qdrant.tech/documentation/
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/qdrant --config-path /etc/qdrant/config.yaml
Restart=on-failure
RestartSec=5
User=root
WorkingDirectory=/var/lib/qdrant

[Install]
WantedBy=multi-user.target
"""


def qdrant_target_version() -> str:
    """Pinned or env override Qdrant release version."""
    override = os.getenv("QDRANT_TARGET_VERSION", "").strip()
    if override:
        return override.lstrip("v")
    return QDRANT_GITHUB_VERSION


def qdrant_linux_arch_suffix() -> Optional[str]:
    """Prebuilt tarball suffix for Qdrant GitHub Releases."""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64-unknown-linux-gnu"
    if machine in ("aarch64", "arm64"):
        return "aarch64-unknown-linux-gnu"
    return None


def qdrant_github_release_url(version: str, arch: str) -> str:
    """GitHub release tarball URL."""
    safe_version = version.lstrip("v")
    return f"https://github.com/qdrant/qdrant/releases/download/v{safe_version}/qdrant-{arch}.tar.gz"


def qdrant_api_responding(timeout: float = 3.0) -> bool:
    """True if Qdrant HTTP API answers on port 6333."""
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:6333/collections",
            timeout=timeout,
        ) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


def stop_qdrant_service() -> bool:
    """Stop systemd qdrant service when unit exists."""
    if not os.path.isfile(QDRANT_SYSTEMD_PATH):
        return True
    try:
        result = subprocess.run(
            ["systemctl", "stop", "qdrant"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def start_qdrant_service() -> bool:
    """Start systemd qdrant service when unit exists."""
    if not os.path.isfile(QDRANT_SYSTEMD_PATH):
        return False
    try:
        subprocess.run(["systemctl", "start", "qdrant"], check=False, timeout=60)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def wait_for_qdrant_api(timeout_seconds: float = 30.0) -> bool:
    """Poll until Qdrant API responds or timeout."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if qdrant_api_responding():
            return True
        time.sleep(1.0)
    return False


def find_qdrant_binary() -> Optional[str]:
    """Return path to an executable qdrant binary if found."""
    for path in (
        QDRANT_LOCAL_BIN,
        "/usr/bin/qdrant",
        os.path.expanduser("~/qdrant/qdrant"),
    ):
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def detect_installed_qdrant_version() -> Optional[str]:
    """Parse `qdrant --version` output."""
    binary = find_qdrant_binary()
    if not binary:
        return None
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout or result.stderr or "").strip()
    match = re.search(r"(\d+\.\d+\.\d+)", output)
    if match:
        return match.group(1)
    return None


def download_url_to_file(url: str, dest: Path) -> bool:
    """Download URL to local path."""
    try:
        with urllib.request.urlopen(url, timeout=300) as response:
            with open(dest, "wb") as outfile:
                shutil.copyfileobj(response, outfile)
        return dest.is_file() and dest.stat().st_size > 0
    except OSError:
        return False


def extract_qdrant_from_tarball(tar_path: Path, dest_bin: Path) -> bool:
    """Extract qdrant binary from release tarball."""
    try:
        with tarfile.open(tar_path, "r:gz") as archive:
            members = archive.getmembers()
            inner = None
            for member in members:
                if member.name.endswith("/qdrant") or member.name == "qdrant":
                    inner = member
                    break
            if inner is None:
                return False
            archive.extract(inner, path=tar_path.parent)
            extracted = tar_path.parent / inner.name
            if not extracted.is_file():
                return False
            dest_bin.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(extracted), str(dest_bin))
            os.chmod(dest_bin, 0o755)
            return True
    except (OSError, tarfile.TarError):
        return False


def ensure_qdrant_systemd_layout() -> None:
    """Write config/systemd unit and create data dirs."""
    os.makedirs("/var/lib/qdrant/storage", mode=0o755, exist_ok=True)
    os.makedirs("/var/lib/qdrant/snapshots", mode=0o755, exist_ok=True)
    os.makedirs("/etc/qdrant", mode=0o755, exist_ok=True)
    with open(QDRANT_CONFIG_PATH, "w", encoding="utf-8") as cfg:
        cfg.write(QDRANT_CONFIG_YAML)
    with open(QDRANT_SYSTEMD_PATH, "w", encoding="utf-8") as unit:
        unit.write(QDRANT_SYSTEMD_UNIT)


def restart_qdrant_service() -> bool:
    """Enable and restart systemd qdrant service when unit exists."""
    if not os.path.isfile(QDRANT_SYSTEMD_PATH):
        return False
    for cmd in (
        ["systemctl", "daemon-reload"],
        ["systemctl", "enable", "qdrant"],
        ["systemctl", "restart", "qdrant"],
    ):
        try:
            subprocess.run(cmd, check=False, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return False
    return True


def install_qdrant_from_tarball(tar_path: Path, *, stop_service: bool = True) -> bool:
    """Install qdrant binary from tarball; optionally stop service before replace."""
    dest = Path(QDRANT_LOCAL_BIN)
    if stop_service:
        stop_qdrant_service()
    if not extract_qdrant_from_tarball(tar_path, dest):
        return False
    ensure_qdrant_systemd_layout()
    if os.path.isfile(QDRANT_SYSTEMD_PATH):
        restart_qdrant_service()
        return wait_for_qdrant_api()
    return True


def download_github_release_to_temp(version: str, arch: str) -> Optional[Path]:
    """Download GitHub release tarball to a temp file."""
    url = qdrant_github_release_url(version, arch)
    tmp_dir = Path(tempfile.mkdtemp(prefix="mg_qdrant_"))
    tar_path = tmp_dir / "qdrant.tgz"
    if download_url_to_file(url, tar_path):
        return tar_path
    return None
