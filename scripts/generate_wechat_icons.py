"""Generate 28px and 108px WeChat icons from the vector favicon."""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GENERATOR = _REPO_ROOT / "frontend" / "scripts" / "generate-pwa-icons.mjs"


def main() -> None:
    """Rasterize all brand icon sizes, including frontend/public/wechat/."""
    completed = subprocess.run(
        ["node", str(_GENERATOR)],
        cwd=_REPO_ROOT / "frontend",
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
