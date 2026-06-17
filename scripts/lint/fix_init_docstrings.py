"""Add one-line module docstrings to __init__.py files that lack them."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    """Main."""
    root = Path(__file__).resolve().parents[2]
    dirs = (
        [root / name for name in sys.argv[1:]]
        if len(sys.argv) > 1
        else [
            root / "services",
            root / "routers",
            root / "agents",
            root / "clients",
            root / "config",
            root / "utils",
        ]
    )
    changed = 0
    for directory in dirs:
        for path in sorted(directory.rglob("__init__.py")):
            source = path.read_text(encoding="utf-8")
            stripped = source.lstrip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            package = path.parent.name.replace("_", " ")
            doc = f'"""{package.title()} package."""\n\n'
            path.write_text(doc + source, encoding="utf-8")
            changed += 1
            print(path.relative_to(root))
    print(f"Updated {changed} __init__.py files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
