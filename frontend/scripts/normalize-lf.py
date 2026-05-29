#!/usr/bin/env python3
"""Convert CRLF/CR to LF in frontend source files (line-ending normalization only)."""
from __future__ import annotations

from pathlib import Path

SKIP_DIRS = frozenset({'node_modules', 'dist'})
EXTENSIONS = frozenset({'.ts', '.vue', '.js', '.css', '.scss', '.json', '.mjs'})


def normalize_file(path: Path) -> bool:
    data = path.read_bytes()
    if b'\r' not in data:
        return False
    normalized = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    path.write_bytes(normalized)
    return True


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    scanned = 0
    converted = 0
    for path in root.rglob('*'):
        if not path.is_file() or path.suffix not in EXTENSIONS:
            continue
        if SKIP_DIRS.intersection(path.parts):
            continue
        scanned += 1
        if normalize_file(path):
            converted += 1
    print(f'scanned={scanned} converted={converted}')


if __name__ == '__main__':
    main()
