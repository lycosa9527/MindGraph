#!/usr/bin/env python3
"""Convert CRLF/CR to LF in repo-level text files used by frontend tooling."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REL_PATHS = (
    '.editorconfig',
    '.vscode/settings.json',
    'docs/NODE_NVM_SETUP.md',
    'frontend/vitest.config.ts',
    'frontend/eslint.config.js',
    'frontend/prettier.config.js',
)


def normalize_file(path: Path) -> bool:
    data = path.read_bytes()
    if b'\r' not in data:
        return False
    path.write_bytes(data.replace(b'\r\n', b'\n').replace(b'\r', b'\n'))
    return True


def main() -> None:
    for rel in REL_PATHS:
        path = REPO_ROOT / rel
        if not path.is_file():
            print(f'skip missing: {rel}')
            continue
        if normalize_file(path):
            print(f'fixed: {rel}')
        else:
            print(f'ok: {rel}')


if __name__ == '__main__':
    main()
