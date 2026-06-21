#!/usr/bin/env python3
"""Run live prompt-requirements smoke via pytest (requires LIVE_LLM=1 and QWEN_API_KEY)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    """Execute live integration tests."""
    env = os.environ.copy()
    env.setdefault("LIVE_LLM", "1")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_prompt_requirements_live.py",
            "-q",
            "-s",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
