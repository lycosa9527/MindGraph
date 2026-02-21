#!/usr/bin/env python3
"""
Qdrant Installation Entry Point

Runs install_dependencies.sh with --qdrant-only. Uses Python to avoid CRLF
line-ending issues when the repo is on a Windows drive and executed from WSL.

Usage:
    python scripts/setup/install_qdrant.py
    sudo python scripts/setup/install_qdrant.py   # for system-level Qdrant install
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    deps_script = script_dir / "install_dependencies.sh"

    if not deps_script.exists():
        print(f"Error: {deps_script} not found", file=sys.stderr)
        return 1

    content = deps_script.read_text(encoding="utf-8")
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    fd, temp_path = tempfile.mkstemp(suffix=".sh", text=True)
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.chmod(temp_path, 0o755)

        cmd = ["bash", temp_path, "--qdrant-only"] + sys.argv[1:]
        result = subprocess.run(cmd)
        return result.returncode
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
