"""Print keys where locale canvas value still equals en (same order)."""
from __future__ import annotations

import re
import sys
from pathlib import Path


def parse(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    body = text.split("export default {", 1)[1].rsplit("}", 1)[0]
    lines = body.splitlines()
    out: list[tuple[str, str]] = []
    idx = 0
    while idx < len(lines):
        match = re.match(r"^\s*'([^']+)':\s*(.*)$", lines[idx].rstrip())
        if not match:
            idx += 1
            continue
        key, rest = match.group(1), match.group(2).strip()
        if rest == "":
            idx += 1
            val_line = lines[idx].strip()
            if val_line.endswith(","):
                val_line = val_line[:-1].strip()
            inner = val_line[1:-1]
            out.append((key, _decode(inner)))
            idx += 1
        else:
            raw = rest[:-1].strip() if rest.endswith(",") else rest.strip()
            inner = raw[1:-1]
            out.append((key, _decode(inner)))
            idx += 1
    return out


def _decode(s: str) -> str:
    res: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            if s[i + 1] == "'":
                res.append("'")
                i += 2
            elif s[i + 1] == "\\":
                res.append("\\")
                i += 2
            else:
                res.append(s[i])
                i += 1
        else:
            res.append(s[i])
            i += 1
    return "".join(res)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "src/locales/messages"
    code = sys.argv[1] if len(sys.argv) > 1 else "sq"
    en_list = parse(root / "en" / "canvas.ts")
    loc_list = parse(root / code / "canvas.ts")
    same = 0
    report = Path(__file__).resolve().parent / f"_canvas_{code}_still_en.txt"
    lines_out: list[str] = []
    for (ek, ev), (lk, lv) in zip(en_list, loc_list, strict=True):
        assert ek == lk
        if ev == lv:
            same += 1
            lines_out.append(f"{ek}\t{ev}")
    report.write_text("\n".join(lines_out), encoding="utf-8")
    print(code, "identical_to_en", same, "of", len(en_list), "->", report.name)


if __name__ == "__main__":
    main()
