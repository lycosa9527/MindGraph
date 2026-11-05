"""
Knowledge Space Request Models
==============================

Pydantic models for Knowledge Space API request validation.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel, Field, model_validator

ChatHandoffPlatform = Literal["wechat", "dingtalk", "wecom"]


class KnowledgeSpaceSettingsUpdateRequest(BaseModel):
    """Request model for updating user Knowledge Space preferences."""

    default_method: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid)$")
    top_k: int = Field(default=5, ge=1, le=20)
    score_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=200)


class ProcessSelectedRequest(BaseModel):
    """Request model for processing selected documents."""

    document_ids: List[int] = Field(..., min_length=1)


class PackageCreateRequest(BaseModel):
    """Request model for creating a File Center package."""

    name: str = Field(..., min_length=1, max_length=200)
    diagram_id: Optional[str] = Field(default=None, max_length=36)
    source: str = Field(default="canvas", pattern="^(canvas|knowledge_space|chrome_extension|doc_summary)$")


class PackageUpdateRequest(BaseModel):
    """Request model for renaming or relinking a package."""

    name: Optional[str] = Field(default=None, max_length=200)
    diagram_id: Optional[str] = Field(default=None, max_length=36)


class PackageIngestTextRequest(BaseModel):
    """Request model for ingesting pasted text into a package."""

    content: str = Field(..., min_length=1, max_length=900_000)
    title: Optional[str] = Field(default=None, max_length=200)
    language: Optional[str] = Field(default=None, max_length=10)
    source_kind: Optional[str] = Field(
        default=None,
        max_length=32,
        pattern="^(paste|voice_notes)$",
    )


class PackageIngestWebRequest(BaseModel):
    """Request model for ingesting a web content snapshot into a package."""

    page_content: str = Field(..., min_length=1, max_length=900_000)
    page_url: Optional[str] = Field(default=None, max_length=2000)
    page_title: Optional[str] = Field(default=None, max_length=300)
    language: Optional[str] = Field(default=None, max_length=10)


class PackageIngestWebUrlRequest(BaseModel):
    """Fetch a public URL server-side and ingest as a web snapshot."""

    page_url: str = Field(..., min_length=1, max_length=2000)
    language: Optional[str] = Field(default=None, max_length=10)


class DocSummarySessionStartRequest(BaseModel):
    """Start or resume a Document Summary session package."""

    diagram_id: Optional[str] = Field(default=None, max_length=36)
    diagram_title: Optional[str] = Field(default=None, max_length=200)
    package_id: Optional[int] = Field(default=None, ge=1)
    create_if_missing: bool = Field(
        default=False,
        description="When true, create a package if none is linked to the session yet.",
    )


class DocSummarySessionClearRequest(BaseModel):
    """Delete the Document Summary package (and COS extract) for a canvas session."""

    diagram_id: Optional[str] = Field(default=None, max_length=36)
    package_id: Optional[int] = Field(default=None, ge=1)


class ChatHandoffStartRequest(BaseModel):
    """Mint a pairing code for file-reader ingest."""

    package_id: int = Field(..., ge=1)


class ChatHandoffCancelRequest(BaseModel):
    """Revoke a waiting pairing code when the diagram session ends."""

    code: Optional[str] = Field(default=None, min_length=6, max_length=6, pattern=r"^\d{6}$")
    package_id: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_code_or_package(self) -> "ChatHandoffCancelRequest":
        """Require at least one of ``code`` or ``package_id``."""
        if not self.code and self.package_id is None:
            raise ValueError("code or package_id is required")
        return self


class ChatHandoffIngestRequest(BaseModel):
    """Ingest chat transcript via pairing code (file-reader client)."""

    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    platform: ChatHandoffPlatform
    chat_title: str = Field(..., min_length=1, max_length=200)
    content: Optional[str] = Field(default=None, max_length=900_000)
    messages: Optional[List[Dict[str, Any]]] = Field(default=None, max_length=5000)
    source_export_name: Optional[str] = Field(default=None, max_length=255)
    language: Optional[str] = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def require_content_or_messages(self) -> "ChatHandoffIngestRequest":
        """Require at least one of ``content`` or ``messages``."""
        has_messages = bool(self.messages)
        has_content = bool((self.content or "").strip())
        if not has_messages and not has_content:
            raise ValueError("Either content or messages is required")
        return self
