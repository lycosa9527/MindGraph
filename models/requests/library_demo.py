"""
Request and response bodies for the signed-in library demo document.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LibraryDemoCaptionModel(BaseModel):
    """Speaker notes and type style for one diagram."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    text: str
    html: str | None = None
    font_size: Literal[15, 18, 22, 28] = Field(alias="fontSize")
    font_face: Literal["sans", "sc", "tc", "serif", "song", "kai", "mono"] = Field(alias="fontFace")
    font_color: Literal["ink", "stone", "brown", "red", "blue", "green"] = Field(default="ink", alias="fontColor")


class LibraryDemoListModel(BaseModel):
    """One named playlist."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    name: str
    diagram_ids: list[str] = Field(alias="diagramIds")
    captions: dict[str, LibraryDemoCaptionModel] = Field(default_factory=dict)


class LibraryDemoThumbnailModel(BaseModel):
    """A list thumbnail, or the revision already covered by the diagram's own image."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    url: str = ""
    updated_at: str = Field(alias="updatedAt")


class LibraryDemoDocumentModel(BaseModel):
    """Playlists plus notes that are not attached to a named list yet."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    lists: list[LibraryDemoListModel] = Field(default_factory=list)
    last_id: str | None = Field(default=None, alias="lastId")
    captions: dict[str, LibraryDemoCaptionModel] = Field(default_factory=dict)
    thumbnails: dict[str, LibraryDemoThumbnailModel] = Field(default_factory=dict)
