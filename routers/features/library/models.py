"""Library Router Models.

Pydantic models for library API requests and responses.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, List
import re

from pydantic import BaseModel, Field, validator


class DocumentResponse(BaseModel):
    """Response model for a library document"""
    id: int
    title: str
    description: Optional[str]
    cover_image_path: Optional[str]
    use_images: bool = False
    pages_dir_path: Optional[str] = None
    total_pages: Optional[int] = None
    views_count: int
    likes_count: int
    comments_count: int
    created_at: str
    uploader: dict


class DocumentListResponse(BaseModel):
    """Response model for document list"""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentCreate(BaseModel):
    """Request model for creating a document (for future admin panel)"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)


class DocumentUpdate(BaseModel):
    """Request model for updating document metadata"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)


class DanmakuCreate(BaseModel):
    """Request model for creating danmaku"""
    content: str = Field(..., min_length=1, max_length=5000)
    page_number: int = Field(..., ge=1)
    position_x: Optional[int] = Field(None, ge=0, le=10000)
    position_y: Optional[int] = Field(None, ge=0, le=10000)
    selected_text: Optional[str] = Field(None, max_length=1000)
    text_bbox: Optional[dict] = None
    color: Optional[str] = None
    highlight_color: Optional[str] = None

    @classmethod
    @validator('color', 'highlight_color')
    def validate_hex_color(cls, v):
        """Validate hex color format."""
        if v is None:
            return v
        if not re.match(r'^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$', v):
            raise ValueError('Invalid hex color format. Use #RRGGBB or #RRGGBBAA')
        return v

    @classmethod
    @validator('text_bbox')
    def validate_text_bbox(cls, v):
        """Validate text bounding box structure."""
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError('text_bbox must be a dictionary')
        required_keys = {'x', 'y', 'width', 'height'}
        if not required_keys.issubset(v.keys()):
            missing = required_keys - set(v.keys())
            raise ValueError(f'text_bbox missing required keys: {missing}')
        # Validate values are numbers
        for key in required_keys:
            if not isinstance(v[key], (int, float)):
                raise ValueError(f'text_bbox.{key} must be a number')
        return v


class ReplyCreate(BaseModel):
    """Request model for creating a reply"""
    content: str = Field(..., min_length=1, max_length=2000)
    parent_reply_id: Optional[int] = None


class DanmakuUpdate(BaseModel):
    """Request model for updating danmaku position"""
    position_x: Optional[int] = None
    position_y: Optional[int] = None


class BookmarkCreate(BaseModel):
    """Request model for creating a bookmark"""
    page_number: int = Field(..., ge=1)
    note: Optional[str] = Field(None, max_length=1000)


class BookRegisterRequest(BaseModel):
    """Request model for registering a book folder"""
    folder_path: str = Field(
        ...,
        description="Path to folder containing page images (relative to storage/library or absolute)"
    )
    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Book title (defaults to folder name)"
    )
    description: Optional[str] = Field(None, max_length=2000, description="Book description")


class BookRegisterBatchRequest(BaseModel):
    """Request model for batch registering book folders"""
    folder_paths: List[str] = Field(..., description="List of folder paths to register")
