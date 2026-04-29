"""Count keys in nl/canvas.ts."""
from __future__ import annotations

import re
from pathlib import Path


def main() -> None:
    text = Path(__file__).resolve().parents[1] / "src/locales/messages/nl/canvas.ts"
    body = text.read_text(encoding="utf-8").split("export default {", 1)[1].rsplit(
        "}", 1
    )[0]
    lines = body.splitlines()
    keys: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx].rstrip()
        match = re.match(r"^(\s*)'([^']+)':\s*(.*)$", line)
        if not match:
            idx += 1
            continue
        key, rest = match.group(2), match.group(3).strip()
        keys.append(key)
        if rest == "":
            idx += 2
        else:
            idx += 1
    print(len(keys))


if __name__ == "__main__":
    main()
