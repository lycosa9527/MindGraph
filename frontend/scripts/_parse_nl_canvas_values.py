"""Decode nl/canvas.ts string values in key order."""
from __future__ import annotations

import re
from pathlib import Path


def decode_ts_string(s: str) -> str:
    out: list[str] = []
    idx = 0
    while idx < len(s):
        if s[idx] == "\\" and idx + 1 < len(s):
            nxt = s[idx + 1]
            if nxt == "'":
                out.append("'")
                idx += 2
            elif nxt == "\\":
                out.append("\\")
                idx += 2
            else:
                out.append(s[idx])
                idx += 1
        else:
            out.append(s[idx])
            idx += 1
    return "".join(out)


def parse_nl(path: Path) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    body = text.split("export default {", 1)[1].rsplit("}", 1)[0]
    lines = body.splitlines()
    keys: list[str] = []
    values: list[str] = []
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
            idx += 1
            val_line = lines[idx].strip()
            if val_line.endswith(","):
                val_line = val_line[:-1].strip()
            assert val_line.startswith("'") and val_line.endswith("'"), val_line
            values.append(decode_ts_string(val_line[1:-1]))
            idx += 1
        else:
            raw = rest
            if raw.endswith(","):
                raw = raw[:-1].strip()
            assert raw.startswith("'") and raw.endswith("'"), raw
            values.append(decode_ts_string(raw[1:-1]))
            idx += 1
    return keys, values


if __name__ == "__main__":
    nl_path = Path(__file__).resolve().parents[1] / "src/locales/messages/nl/canvas.ts"
    ks, vs = parse_nl(nl_path)
    print(len(ks), len(vs))
    euler_i = ks.index("canvas.toolbar.mathKeyboardEqEuler")
    abs_i = ks.index("canvas.toolbar.mathKeyboardEqAbsX")
    print("euler", repr(vs[euler_i]))
    print("abs", repr(vs[abs_i]))
