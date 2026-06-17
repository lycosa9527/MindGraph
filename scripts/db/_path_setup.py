"""Add project root to sys.path for scripts run from scripts/db/."""

import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

_env_path = project_root / ".env"
if _env_path.is_file():
    with open(_env_path, encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, value = stripped.partition("=")
                os.environ.setdefault(key.strip(), value.strip().split("#")[0].strip())
