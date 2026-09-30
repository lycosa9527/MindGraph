"""
Operator entry point for a Dify database dump and history merge.

Run on the host where the Dify stack is up::

    python -m scripts.dify.db_merge

The prompts find the compose file, check that Postgres is using the data
directory from that file, scan workflows, then dump or move chat history.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import sys

from scripts.dify.db_merge.models import ComposeError, PlanError, SchemaError
from scripts.dify.db_merge.wizard import run_interactive


def main(argv: list[str] | None = None) -> int:
    """Prompt for a dump or merge. Extra arguments are refused."""
    args = sys.argv[1:] if argv is None else list(argv)
    if args:
        print("Run with no arguments: python -m scripts.dify.db_merge", file=sys.stderr)
        return 2
    try:
        run_interactive()
    except PlanError as exc:
        print(exc, file=sys.stderr)
        return 2
    except (ComposeError, SchemaError) as exc:
        print(exc, file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return 2
    return 0
