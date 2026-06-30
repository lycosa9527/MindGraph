#!/usr/bin/env python3
"""Redirect to scripts/db/update_stack_from_cos.py (canonical location)."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    _target = Path(__file__).resolve().parents[1] / "db" / "update_stack_from_cos.py"
    runpy.run_path(str(_target), run_name="__main__")
