"""Regenerate extension PNG icons from frontend/public/favicon.svg."""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GENERATOR = _REPO_ROOT / "frontend" / "scripts" / "generate-pwa-icons.mjs"


def main() -> None:
    """Rasterize Chrome/Edge icon sizes via the shared vector pipeline."""
    completed = subprocess.run(
        ["node", str(_GENERATOR)],
        cwd=_REPO_ROOT / "frontend",
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
