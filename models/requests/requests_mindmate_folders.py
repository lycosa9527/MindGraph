"""Request models for MindMate conversation folders."""

from typing import Optional

from pydantic import BaseModel, Field


class MindmateFolderCreateRequest(BaseModel):
    """Request model for creating a MindMate archive folder."""

    name: str = Field(..., min_length=1, max_length=100, description="Folder name")


class MindmateFolderUpdateRequest(BaseModel):
    """Request model for renaming a MindMate archive folder."""

    name: str = Field(..., min_length=1, max_length=100, description="New folder name")


class MindmateMoveFolderRequest(BaseModel):
    """Move a conversation into a folder, or back to uncategorized."""

    folder_id: Optional[str] = Field(
        None,
        description="Target folder UUID; null removes the conversation from its folder",
    )
