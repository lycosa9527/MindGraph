"""Download a published zip, check its hash, and swap the install folder after quit."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import urllib.request
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Hex digest of a downloaded zip."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def download(url: str, dest: Path) -> None:
    """Save the presigned zip. The caller checks the hash before install."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)


def hash_matches(path: Path, expected: str) -> bool:
    """False deletes nothing by itself. The caller must refuse the install."""
    return sha256_file(path).lower() == expected.strip().lower()


def _detach(command: list[str]) -> None:
    executable = shutil.which(command[0]) or command[0]
    os.spawnv(os.P_NOWAIT, executable, command)


def launch_swap(zip_path: Path) -> None:
    """Quit is the caller's job. This starts a helper that replaces the folder after the app exits."""
    root = install_root()
    if sys.platform == "win32":
        script = root / "apply-update.bat"
        exe = root / "MindGraph Pet.exe"
        script.write_text(
            f'@echo off\r\ntimeout /t 2 /nobreak >nul\r\ntar -xf "{zip_path}" -C "{root}"\r\nstart "" "{exe}"\r\n',
            encoding="utf-8",
        )
        _detach(["cmd", "/c", str(script)])
        return
    script = root / "apply-update.sh"
    script.write_text(
        f'#!/bin/sh\nsleep 2\nditto -x -k "{zip_path}" "{root}"\nopen -a "MindGraph Pet"\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    _detach(["/bin/sh", str(script)])


def install_root() -> Path:
    """The real app folder, not PyInstaller's temporary unpack directory."""
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        if sys.platform == "darwin":
            # MindGraph Pet.app/Contents/MacOS/executable
            return executable.parents[2]
        return executable.parent
    return Path(__file__).resolve().parents[1]
