"""Compare canvas.ts key counts."""
from __future__ import annotations

import re
from pathlib import Path


def count_keys(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    body = text.split("export default {", 1)[1].rsplit("}", 1)[0]
    lines = body.splitlines()
    keys = 0
    idx = 0
    while idx < len(lines):
        match = re.match(r"^\s*'([^']+)':\s*(.*)$", lines[idx].rstrip())
        if not match:
            idx += 1
            continue
        keys += 1
        rest = match.group(2).strip()
        if rest == "":
            idx += 2
        else:
            idx += 1
    return keys


root = Path(__file__).resolve().parents[1] / "src/locales/messages"
for name in ("es", "nl", "pl", "de", "it"):
    p = root / name / "canvas.ts"
    if p.exists():
        print(name, count_keys(p))
