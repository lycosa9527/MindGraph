"""Repair broken workshop.ts locale files after mojibake / U+FFFD corruption.

Restores terminators: U+FFFD + "?" before comma often replaced a lost "'" or "…".
Fixes merged workshopCanvas lines and normalizes newlines.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend" / "src" / "locales" / "messages"

# Keys whose English source ends with three ASCII dots (not U+2026 ellipsis).
THREE_DOT_KEYS = {
    "workshop.newMessage",
    "workshop.searchMembers",
    "workshop.searchMessages",
    "workshop.topicDescriptionPlaceholder",
    "workshop.typeMessagePlaceholder",
}

BROKEN_TAIL = re.compile(
    r"^(\s*)('(?:[\w.]+)')\s*:\s*'(.*)\ufffd\?\s*,\s*$"
)

MERGED_USERLEFT = re.compile(
    r"^(\s*)('workshopCanvas\.usersJoined')\s*:\s*"
    r"('\{count\} users joined'),workshopCanvas\.userLeft'\s*:\s*'(.*)$"
)

KEY_SINGLE_SQ = re.compile(r"^(\s*'[\w.]+\'\s*:\s*')(.+)$")
KEY_SINGLE_DQ = re.compile(r'^(\s*\'[\w.]+\'\s*:\s*")(.+)$')
CONT_VALUE = re.compile(r"^(\s+)'(.+)$")


def fix_unterminated(line: str) -> str:
    s = line.rstrip()
    m = KEY_SINGLE_SQ.match(s)
    if m and s.endswith(","):
        prefix, rest = m.group(1), m.group(2)
        if rest.endswith("',"):
            return line
        if rest.endswith(","):
            return prefix + rest[:-1] + "',"
        return line
    m = KEY_SINGLE_DQ.match(s)
    if m and s.endswith(","):
        prefix, rest = m.group(1), m.group(2)
        if rest.endswith('",'):
            return line
        if rest.endswith(","):
            return prefix + rest[:-1] + '",'
        return line
    m = CONT_VALUE.match(s)
    if m:
        indent, body = m.group(1), m.group(2)
        if body.endswith("',") or body.endswith('",'):
            return line
        if body.endswith(","):
            return f"{indent}'{body[:-1]}',"
    return line


def fix_line(line: str) -> list[str]:
    mm = MERGED_USERLEFT.match(line)
    if mm:
        indent, qkey = mm.group(1), mm.group(2)
        count_lit, rest_value = mm.group(3), mm.group(4)
        if rest_value.endswith("',"):
            rest_value = rest_value[:-2]
        rest_value = rest_value.replace("\ufffd?", "")
        line1 = f"{indent}{qkey}: {count_lit},"
        line2 = f"{indent}'workshopCanvas.userLeft': '{rest_value}',"
        return [line1, line2]
    m = BROKEN_TAIL.match(line)
    if m:
        indent, qkey, value = m.group(1), m.group(2), m.group(3)
        key_inner = qkey.strip("'")
        suffix = "...'," if key_inner in THREE_DOT_KEYS else "…',"
        return [f"{indent}{qkey}: '{value}{suffix}"]
    if re.match(r"^\s*',\s*$", line):
        return []
    return [line]


def fix_text_once(text: str) -> str:
    text = text.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
    stage: list[str] = []
    for line in text.split("\n"):
        stage.extend(fix_line(line))
    out = [fix_unterminated(ln) for ln in stage]
    joined = "\n".join(out)
    dropped = joined.replace("\ufffd?", "")
    return dropped


def fix_text(path: Path) -> str:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    prev = None
    cur = text
    while cur != prev:
        prev = cur
        cur = fix_text_once(cur)
    return cur


def main() -> None:
    for wsh in sorted(ROOT.glob("*/workshop.ts")):
        if wsh.parent.name == "en":
            continue
        before = wsh.read_text(encoding="utf-8")
        after = fix_text(wsh)
        if after != before:
            wsh.write_text(after, encoding="utf-8", newline="\n")
            print("fixed", wsh.parent.name)


if __name__ == "__main__":
    main()
