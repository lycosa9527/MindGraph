"""Verify nl and es canvas share key order."""
from __future__ import annotations

import re
from pathlib import Path


def keys_in_order(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    body = text.split("export default {", 1)[1].rsplit("}", 1)[0]
    lines = body.splitlines()
    out: list[str] = []
    idx = 0
    while idx < len(lines):
        match = re.match(r"^\s*'([^']+)':\s*(.*)$", lines[idx].rstrip())
        if not match:
            idx += 1
            continue
        out.append(match.group(1))
        if match.group(2).strip() == "":
            idx += 2
        else:
            idx += 1
    return out


root = Path(__file__).resolve().parents[1] / "src/locales/messages"
nk = keys_in_order(root / "nl" / "canvas.ts")
ek = keys_in_order(root / "es" / "canvas.ts")
print("same", nk == ek)
if nk != ek:
    for i, (a, b) in enumerate(zip(nk, ek)):
        if a != b:
            print("diff at", i, a, b)
            break
