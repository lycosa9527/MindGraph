# Mirrors chrome-extension/doc-extract/smartedu/models.js — keep asset fields in sync.

"""SmartEdu asset dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SmartEduAsset:
    """One downloadable lesson asset."""

    asset_id: str
    title: str
    alias: str
    resource_type: str
    format: str
    download_url: str
    selected: bool = True
    local_path: Optional[Path] = None
    error: Optional[str] = None


@dataclass
class SmartEduLesson:
    """Parsed lesson metadata with flat asset list."""

    lesson_id: str
    title: str
    detail_url: str
    assets: list[SmartEduAsset] = field(default_factory=list)
