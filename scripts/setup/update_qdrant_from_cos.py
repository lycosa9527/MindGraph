#!/usr/bin/env python3
"""Redirect to scripts/db/update_stack_from_cos.py (canonical location)."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    _target = Path(__file__).resolve().parents[1] / "db" / "update_stack_from_cos.py"
    # `python script.py` puts the script directory on sys.path. runpy.run_path does not,
    # so sibling imports such as `_path_setup` fail when this shim is the entry point.
    sys.path.insert(0, str(_target.parent))
    runpy.run_path(str(_target), run_name="__main__")
