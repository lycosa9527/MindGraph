"""
Parse Keep a Changelog-style Markdown for recent version sections.
"""

from __future__ import annotations

from typing import List, TypedDict


class ChangelogEntryDict(TypedDict):
    """One version block from CHANGELOG.md."""

    title: str
    body: str


def extract_recent_changelog_entries(text: str, limit: int) -> List[ChangelogEntryDict]:
    """
    Return the first `limit` sections whose headings match `## [version]`.

    Subsections use `###` and do not break version blocks. The next `## `
    line (typically another release) ends the current section.
    """
    if limit < 1:
        return []

    lines = text.splitlines()
    entries: List[ChangelogEntryDict] = []
    idx = 0
    while idx < len(lines) and len(entries) < limit:
        line = lines[idx]
        if line.startswith("## [") and "]" in line:
            title = line[3:].strip()
            idx += 1
            body_lines: List[str] = []
            while idx < len(lines):
                nxt = lines[idx]
                if nxt.startswith("## ") and not nxt.startswith("###"):
                    break
                body_lines.append(nxt)
                idx += 1
            body = "\n".join(body_lines).strip()
            entries.append({"title": title, "body": body})
            continue
        idx += 1

    return entries
