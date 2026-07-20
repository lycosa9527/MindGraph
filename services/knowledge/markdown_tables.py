"""Helpers for building GitHub-flavored markdown tables from row data.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence


def _cell_text(value: object) -> str:
    """Normalize a cell value for markdown table output."""
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("|", "\\|").strip()
    return text


def rows_to_markdown_table(rows: Sequence[Sequence[object]]) -> str:
    """Convert a rectangular sequence of rows into a GFM markdown table.

    The first non-empty row is treated as the header. Empty tables return ``""``.
    """
    normalized: List[List[str]] = []
    for row in rows:
        cells = [_cell_text(cell) for cell in row]
        if any(cells):
            normalized.append(cells)
    if not normalized:
        return ""

    width = max(len(row) for row in normalized)
    padded = [row + [""] * (width - len(row)) for row in normalized]
    header = padded[0]
    body = padded[1:] if len(padded) > 1 else []
    if not body:
        # Single-row sheet: synthesize a header so GFM still renders a table.
        header = [f"Col {index + 1}" for index in range(width)]
        body = padded

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def sheet_to_markdown(sheet_name: str, rows: Iterable[Sequence[object]]) -> Optional[str]:
    """Build a markdown section for one spreadsheet sheet."""
    table = rows_to_markdown_table(list(rows))
    if not table:
        return None
    return f"## {sheet_name}\n\n{table}"
