"""WeChat manual folder export listing."""

from __future__ import annotations

from pathlib import Path
from typing import List

from file_reader.chat.messages import ExportPreview, parse_text_export_file


def list_export_files(root: Path) -> List[ExportPreview]:
    """List ``.md`` and legacy ``.txt`` chat exports under a directory."""
    if not root.is_dir():
        return []
    previews: List[ExportPreview] = []
    seen: set[Path] = set()
    candidates: List[Path] = []
    for pattern in ("*.md", "*.txt"):
        candidates.extend(root.rglob(pattern))
    for path in sorted(candidates, key=lambda item: str(item).lower()):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        messages = parse_text_export_file(path)
        title = path.stem.replace("_", " ")
        previews.append(ExportPreview(title=title, path=path, message_count=len(messages)))
    return previews


def parse_export_file(path: Path, max_messages: int = 5000):
    """Backward-compatible alias for folder export parsing."""
    return parse_text_export_file(path, max_messages=max_messages)
