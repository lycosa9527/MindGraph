"""
Library Models for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Database models for public library feature with PDF viewing and danmaku comments.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime
import uuid
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Index, JSON, UniqueConstraint
from sqlalchemy.orm import relationship

from models.domain.auth import Base


def generate_uuid():
    """Generate a UUID string for bookmark IDs."""
    return str(uuid.uuid4())


class LibraryDocument(Base):
    """
    Library document model.

    Represents a document in the public library.
    Can be either a PDF document or an image-based document (pages exported as images).
    Documents are managed manually (uploaded to storage/library/).
    """
    __tablename__ = "library_documents"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    
    # Document info
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=False)  # Storage path (legacy/placeholder, not used for image-based docs)
    file_size = Column(Integer, nullable=False)  # Bytes (legacy, not used for image-based docs)
    cover_image_path = Column(String(500), nullable=True)  # Cover image path
    
    # Image-based document support
    use_images = Column(Boolean, default=False, nullable=False)  # Flag indicating if document uses images instead of PDF
    pages_dir_path = Column(String(500), nullable=True)  # Path to directory containing page images
    total_pages = Column(Integer, nullable=True)  # Total number of pages (for image-based docs)
    
    # Uploader info
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Engagement metrics
    views_count = Column(Integer, default=0, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    comments_count = Column(Integer, default=0, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    uploader = relationship("User")
    danmaku = relationship("LibraryDanmaku", back_populates="document", cascade="all, delete-orphan")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_library_documents_created', 'created_at'),
        Index('ix_library_documents_active', 'is_active'),
        Index('ix_library_documents_pages_dir', 'pages_dir_path'),
    )
    
    def __repr__(self):
        return f"<LibraryDocument id={self.id} title={self.title[:30]}>"


class LibraryDanmaku(Base):
    """
    Danmaku/comment on library PDF documents.
    
    Supports two modes:
    1. Text selection mode: Comments on selected text (for OCRed PDFs)
    2. Position mode: Comments at specific coordinates (fallback)
    """
    __tablename__ = "library_danmaku"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("library_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Page info
    page_number = Column(Integer, nullable=False, index=True)  # 1-indexed
    
    # Position mode (fallback)
    position_x = Column(Integer, nullable=True)  # X coordinate or percentage
    position_y = Column(Integer, nullable=True)  # Y coordinate or percentage
    
    # Text selection mode (for OCRed PDFs)
    selected_text = Column(Text, nullable=True)  # The actual text content selected
    text_bbox = Column(JSON, nullable=True)  # Bounding box: {x, y, width, height} relative to page
    
    # Comment content
    content = Column(Text, nullable=False)
    color = Column(String(20), nullable=True)  # Danmaku color
    highlight_color = Column(String(20), nullable=True)  # Highlight color for text selections
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("LibraryDocument", back_populates="danmaku")
    user = relationship("User")
    likes = relationship("LibraryDanmakuLike", back_populates="danmaku", cascade="all, delete-orphan")
    replies = relationship("LibraryDanmakuReply", back_populates="danmaku", cascade="all, delete-orphan")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_library_danmaku_document_page', 'document_id', 'page_number'),
        Index('ix_library_danmaku_created', 'created_at'),
        Index('ix_library_danmaku_selected_text', 'selected_text'),
    )
    
    def __repr__(self):
        return f"<LibraryDanmaku id={self.id} document_id={self.document_id} page={self.page_number}>"


class LibraryDanmakuLike(Base):
    """
    Likes on library danmaku/comments.
    
    One like per user per danmaku.
    """
    __tablename__ = "library_danmaku_likes"
    
    id = Column(Integer, primary_key=True, index=True)
    danmaku_id = Column(Integer, ForeignKey("library_danmaku.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    danmaku = relationship("LibraryDanmaku", back_populates="likes")
    user = relationship("User")
    
    # Unique constraint: one like per user per danmaku
    __table_args__ = (
        Index('ix_library_danmaku_likes_unique', 'danmaku_id', 'user_id', unique=True),
    )
    
    def __repr__(self):
        return f"<LibraryDanmakuLike danmaku_id={self.danmaku_id} user_id={self.user_id}>"


class LibraryDanmakuReply(Base):
    """
    Threaded replies to library danmaku/comments.
    
    Supports nested replies via parent_reply_id.
    """
    __tablename__ = "library_danmaku_replies"
    
    id = Column(Integer, primary_key=True, index=True)
    danmaku_id = Column(Integer, ForeignKey("library_danmaku.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    parent_reply_id = Column(Integer, ForeignKey("library_danmaku_replies.id", ondelete="CASCADE"), nullable=True, index=True)  # For nested replies
    content = Column(Text, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    danmaku = relationship("LibraryDanmaku", back_populates="replies")
    user = relationship("User")
    parent_reply = relationship("LibraryDanmakuReply", remote_side=[id], backref="child_replies")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_library_danmaku_replies_danmaku', 'danmaku_id', 'created_at'),
        Index('ix_library_danmaku_replies_parent', 'parent_reply_id'),
    )
    
    def __repr__(self):
        return f"<LibraryDanmakuReply id={self.id} danmaku_id={self.danmaku_id}>"


class LibraryBookmark(Base):
    """
    Bookmarks for library PDF documents.
    
    Users can bookmark specific pages in documents for quick access.
    Uses UUID for secure, non-guessable bookmark identification.
    """
    __tablename__ = "library_bookmarks"
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    # uuid has unique=True which creates a UNIQUE constraint (implemented as UNIQUE INDEX)
    # No need for index=True or explicit Index - unique=True already creates the index
    uuid = Column(String(36), nullable=False, unique=True, default=generate_uuid)  # UUID for tracking/sharing
    document_id = Column(Integer, ForeignKey("library_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Page info
    page_number = Column(Integer, nullable=False, index=True)  # 1-indexed
    
    # Optional note/description
    note = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("LibraryDocument")
    user = relationship("User")
    
    # Unique constraint: one bookmark per user per document per page
    __table_args__ = (
        UniqueConstraint('document_id', 'user_id', 'page_number', name='uq_library_bookmark_doc_user_page'),
        Index('ix_library_bookmarks_user_created', 'user_id', 'created_at'),
        Index('ix_library_bookmark_doc_page', 'document_id', 'page_number'),
        # Removed Index('ix_library_bookmarks_uuid', 'uuid') - redundant with unique=True on uuid column
    )
    
    def __repr__(self):
        return f"<LibraryBookmark id={self.id} uuid={self.uuid} document_id={self.document_id} page={self.page_number}>"
