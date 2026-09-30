"""
Plan and connection types for a Dify history merge.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PlanError(ValueError):
    """The operator's paths or plan cannot be used."""


class ComposeError(RuntimeError):
    """Docker Compose, pg_dump, or psql failed."""


class SchemaError(RuntimeError):
    """This Dify database is missing columns the merge needs."""


@dataclass(frozen=True)
class SourceMove:
    """One school app whose chat rows move onto the target app."""

    app_id: str
    persona: dict[str, str]


@dataclass(frozen=True)
class MergePlan:
    """In-place history move. ``execute`` commits; otherwise the SQL rolls back."""

    target_app_id: str
    sources: tuple[SourceMove, ...]
    execute: bool


@dataclass(frozen=True)
class ComposeTarget:
    """One Dify compose project and the Postgres service inside it."""

    compose_dir: Path
    compose_file: Path
    project_name: str
    db_user: str
    db_name: str
    service: str

    def command(self, args: list[str]) -> list[str]:
        """Docker Compose argv, including the postgresql profile."""
        base = [
            "docker",
            "compose",
            "-f",
            str(self.compose_file),
            "--project-directory",
            str(self.compose_dir),
            "--profile",
            "postgresql",
        ]
        if self.project_name:
            base.extend(["--project-name", self.project_name])
        return base + args
