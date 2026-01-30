"""
Library Service Tests
=====================

Unit tests for library functionality including:
- Document registration and retrieval
- Danmaku CRUD operations
- Bookmark operations
- Path resolution edge cases
- Error handling paths

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path
from datetime import datetime

from services.library import LibraryService
from services.library.exceptions import (
    DocumentNotFoundError,
    PageNotFoundError,
    PageImageNotFoundError,
    PagesDirectoryNotFoundError,
    DocumentNotImageBasedError
)
from models.domain.library import LibraryDocument, LibraryDanmaku, LibraryBookmark


class TestLibraryService:
    """Test LibraryService initialization and basic operations."""
    
    def test_service_initialization(self):
        """Test that LibraryService initializes correctly."""
        db_mock = Mock()
        service = LibraryService(db_mock, user_id=1)
        
        assert service.db == db_mock
        assert service.user_id == 1
        assert service.storage_dir is not None
        assert service.covers_dir is not None
    
    def test_service_initialization_without_user_id(self):
        """Test that LibraryService can be initialized without user_id."""
        db_mock = Mock()
        service = LibraryService(db_mock)
        
        assert service.db == db_mock
        assert service.user_id is None


class TestLibraryDocumentOperations:
    """Test document-related operations."""
    
    @pytest.fixture
    def db_mock(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def service(self, db_mock):
        """Create a LibraryService instance."""
        return LibraryService(db_mock, user_id=1)
    
    @pytest.fixture
    def mock_document(self):
        """Create a mock LibraryDocument."""
        doc = Mock(spec=LibraryDocument)
        doc.id = 1
        doc.title = "Test Document"
        doc.description = "Test Description"
        doc.use_images = True
        doc.total_pages = 10
        doc.pages_dir_path = "storage/library/test_book"
        doc.is_active = True
        doc.views_count = 0
        doc.likes_count = 0
        doc.comments_count = 0
        doc.created_at = datetime.utcnow()
        doc.uploader_id = 1
        doc.uploader = Mock()
        doc.uploader.name = "Test User"
        return doc
    
    def test_get_document_not_found(self, service, db_mock):
        """Test getting a non-existent document."""
        db_mock.query.return_value.filter.return_value.first.return_value = None
        
        result = service.get_document(999)
        
        assert result is None
    
    def test_get_document_success(self, service, db_mock, mock_document):
        """Test getting an existing document."""
        db_mock.query.return_value.filter.return_value.first.return_value = mock_document
        
        result = service.get_document(1)
        
        assert result == mock_document
        assert result.id == 1
        assert result.title == "Test Document"
    
    def test_increment_views(self, service, db_mock, mock_document):
        """Test incrementing document view count."""
        db_mock.query.return_value.filter.return_value.first.return_value = mock_document
        mock_document.views_count = 5
        
        service.increment_views(1)
        
        assert mock_document.views_count == 6
        db_mock.commit.assert_called_once()
    
    def test_increment_views_document_not_found(self, service, db_mock):
        """Test incrementing views for non-existent document."""
        db_mock.query.return_value.filter.return_value.first.return_value = None
        
        service.increment_views(999)
        
        # Should not raise error, just do nothing
        db_mock.commit.assert_not_called()


class TestLibraryDanmakuOperations:
    """Test danmaku-related operations."""
    
    @pytest.fixture
    def db_mock(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def service(self, db_mock):
        """Create a LibraryService instance."""
        return LibraryService(db_mock, user_id=1)
    
    @pytest.fixture
    def mock_document(self):
        """Create a mock LibraryDocument."""
        doc = Mock(spec=LibraryDocument)
        doc.id = 1
        doc.comments_count = 0
        return doc
    
    @pytest.fixture
    def mock_danmaku(self):
        """Create a mock LibraryDanmaku."""
        danmaku = Mock(spec=LibraryDanmaku)
        danmaku.id = 1
        danmaku.document_id = 1
        danmaku.user_id = 1
        danmaku.page_number = 1
        danmaku.content = "Test comment"
        danmaku.created_at = datetime.utcnow()
        danmaku.is_active = True
        return danmaku
    
    def test_create_danmaku_success(self, service, db_mock, mock_document):
        """Test creating a danmaku successfully."""
        db_mock.query.return_value.filter.return_value.first.return_value = mock_document
        
        with patch('services.library.library_danmaku_mixin.LibraryDanmaku') as DanmakuMock:
            new_danmaku = Mock()
            new_danmaku.id = 1
            DanmakuMock.return_value = new_danmaku
            
            result = service.create_danmaku(
                document_id=1,
                content="Test comment",
                page_number=1
            )
            
            assert result == new_danmaku
            assert mock_document.comments_count == 1
            db_mock.add.assert_called()
            db_mock.commit.assert_called_once()
    
    def test_create_danmaku_document_not_found(self, service, db_mock):
        """Test creating danmaku for non-existent document."""
        db_mock.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="Document.*not found"):
            service.create_danmaku(
                document_id=999,
                content="Test comment",
                page_number=1
            )
    
    def test_get_danmaku_empty_list(self, service, db_mock):
        """Test getting danmaku when none exist."""
        db_mock.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db_mock.query.return_value.filter.return_value.options.return_value.order_by.return_value.all.return_value = []
        
        result = service.get_danmaku(document_id=1)
        
        assert result == []
    
    def test_toggle_like_create(self, service, db_mock, mock_danmaku):
        """Test toggling like when not already liked."""
        # Mock danmaku query
        danmaku_query = Mock()
        danmaku_query.filter.return_value.first.return_value = mock_danmaku
        
        # Mock like query - no existing like
        like_query = Mock()
        like_query.filter.return_value.first.return_value = None
        
        # Mock count query
        count_query = Mock()
        count_query.filter.return_value.group_by.return_value.all.return_value = []
        
        db_mock.query.side_effect = [danmaku_query, like_query, count_query]
        
        result = service.toggle_like(1)
        
        assert result["is_liked"] is True
        db_mock.add.assert_called()
        db_mock.commit.assert_called_once()


class TestLibraryBookmarkOperations:
    """Test bookmark-related operations."""
    
    @pytest.fixture
    def db_mock(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def service(self, db_mock):
        """Create a LibraryService instance."""
        return LibraryService(db_mock, user_id=1)
    
    @pytest.fixture
    def mock_bookmark(self):
        """Create a mock LibraryBookmark."""
        bookmark = Mock(spec=LibraryBookmark)
        bookmark.id = 1
        bookmark.document_id = 1
        bookmark.user_id = 1
        bookmark.page_number = 5
        bookmark.note = "Test note"
        bookmark.created_at = datetime.utcnow()
        return bookmark
    
    def test_create_bookmark_success(self, service, db_mock):
        """Test creating a bookmark successfully."""
        # Mock query - bookmark doesn't exist yet
        db_mock.query.return_value.filter.return_value.first.return_value = None
        
        with patch('services.library.library_bookmark_mixin.LibraryBookmark') as BookmarkMock:
            new_bookmark = Mock()
            new_bookmark.id = 1
            BookmarkMock.return_value = new_bookmark
            
            result = service.create_bookmark(
                document_id=1,
                page_number=5,
                note="Test note"
            )
            
            assert result == new_bookmark
            db_mock.add.assert_called()
            db_mock.commit.assert_called_once()
    
    def test_create_bookmark_update_existing(self, service, db_mock, mock_bookmark):
        """Test updating an existing bookmark."""
        db_mock.query.return_value.filter.return_value.first.return_value = mock_bookmark
        
        result = service.create_bookmark(
            document_id=1,
            page_number=5,
            note="Updated note"
        )
        
        assert result == mock_bookmark
        assert mock_bookmark.note == "Updated note"
        db_mock.commit.assert_called_once()
    
    def test_create_bookmark_no_user_id(self, db_mock):
        """Test creating bookmark without user_id raises error."""
        service = LibraryService(db_mock)  # No user_id
        
        with pytest.raises(ValueError, match="User ID required"):
            service.create_bookmark(document_id=1, page_number=1)
    
    def test_delete_bookmark_success(self, service, db_mock, mock_bookmark):
        """Test deleting a bookmark successfully."""
        db_mock.query.return_value.filter.return_value.first.return_value = mock_bookmark
        
        result = service.delete_bookmark(1)
        
        assert result is True
        db_mock.delete.assert_called_once_with(mock_bookmark)
        db_mock.commit.assert_called_once()
    
    def test_delete_bookmark_not_found(self, service, db_mock):
        """Test deleting a non-existent bookmark."""
        db_mock.query.return_value.filter.return_value.first.return_value = None
        
        result = service.delete_bookmark(999)
        
        assert result is False
        db_mock.delete.assert_not_called()


class TestLibraryPathResolution:
    """Test path resolution utilities."""
    
    def test_normalize_library_path_in_storage(self):
        """Test normalizing a path within storage directory."""
        from services.library.library_path_utils import normalize_library_path
        
        storage_dir = Path("/project/storage/library")
        project_root = Path("/project")
        file_path = Path("/project/storage/library/test_book/page1.jpg")
        
        result = normalize_library_path(file_path, storage_dir, project_root)
        
        assert result == "storage/library/test_book/page1.jpg"
    
    def test_resolve_library_path_relative(self):
        """Test resolving a relative library path."""
        from services.library.library_path_utils import resolve_library_path
        
        storage_dir = Path("/project/storage/library")
        project_root = Path("/project")
        pages_dir_path = "storage/library/test_book"
        
        with patch('pathlib.Path.exists', return_value=True):
            result = resolve_library_path(pages_dir_path, storage_dir, project_root)
            
            assert result is not None
            assert isinstance(result, Path)


class TestLibraryErrorHandling:
    """Test error handling and custom exceptions."""
    
    def test_document_not_found_error(self):
        """Test DocumentNotFoundError exception."""
        error = DocumentNotFoundError(123)
        
        assert error.document_id == 123
        assert error.error_code == "DOCUMENT_NOT_FOUND"
        assert "123" in error.message
        assert error.context["document_id"] == 123
    
    def test_page_not_found_error(self):
        """Test PageNotFoundError exception."""
        error = PageNotFoundError(document_id=1, page_number=100, total_pages=10)
        
        assert error.document_id == 1
        assert error.page_number == 100
        assert error.total_pages == 10
        assert error.error_code == "PAGE_NOT_FOUND"
        assert "exceeds" in error.message.lower()
    
    def test_page_image_not_found_error(self):
        """Test PageImageNotFoundError exception."""
        error = PageImageNotFoundError(document_id=1, page_number=5, image_path="/path/to/image.jpg")
        
        assert error.document_id == 1
        assert error.page_number == 5
        assert error.image_path == "/path/to/image.jpg"
        assert error.error_code == "PAGE_IMAGE_NOT_FOUND"
    
    def test_document_not_image_based_error(self):
        """Test DocumentNotImageBasedError exception."""
        error = DocumentNotImageBasedError(123)
        
        assert error.document_id == 123
        assert error.error_code == "DOCUMENT_NOT_IMAGE_BASED"
        assert "does not use images" in error.message.lower()
    
    def test_pages_directory_not_found_error(self):
        """Test PagesDirectoryNotFoundError exception."""
        error = PagesDirectoryNotFoundError(1, "/path/to/pages")
        
        assert error.document_id == 1
        assert error.pages_dir_path == "/path/to/pages"
        assert error.error_code == "PAGES_DIRECTORY_NOT_FOUND"


class TestLibraryInputSanitization:
    """Test input sanitization."""
    
    @pytest.fixture
    def db_mock(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def service(self, db_mock):
        """Create a LibraryService instance."""
        return LibraryService(db_mock, user_id=1)
    
    def test_sanitize_content_removes_html(self, service):
        """Test that HTML tags are removed from content."""
        from services.library.library_danmaku_mixin import LibraryDanmakuMixin
        
        mixin = LibraryDanmakuMixin()
        mixin.db = service.db
        mixin.user_id = service.user_id
        
        content = "<script>alert('xss')</script>Hello World"
        sanitized = mixin._sanitize_content(content)
        
        assert "<script>" not in sanitized
        assert "alert" not in sanitized
        assert "Hello World" in sanitized
    
    def test_sanitize_content_removes_javascript(self, service):
        """Test that javascript: protocol is removed."""
        from services.library.library_danmaku_mixin import LibraryDanmakuMixin
        
        mixin = LibraryDanmakuMixin()
        mixin.db = service.db
        mixin.user_id = service.user_id
        
        content = "javascript:alert('xss')"
        sanitized = mixin._sanitize_content(content)
        
        assert "javascript:" not in sanitized.lower()
    
    def test_sanitize_content_removes_event_handlers(self, service):
        """Test that on* event handlers are removed."""
        from services.library.library_danmaku_mixin import LibraryDanmakuMixin
        
        mixin = LibraryDanmakuMixin()
        mixin.db = service.db
        mixin.user_id = service.user_id
        
        content = "onclick=alert('xss') Hello"
        sanitized = mixin._sanitize_content(content)
        
        assert "onclick" not in sanitized.lower()
        assert "Hello" in sanitized
    
    def test_sanitize_content_none_returns_none(self, service):
        """Test that None input returns None."""
        from services.library.library_danmaku_mixin import LibraryDanmakuMixin
        
        mixin = LibraryDanmakuMixin()
        mixin.db = service.db
        mixin.user_id = service.user_id
        
        result = mixin._sanitize_content(None)
        
        assert result is None


class TestLibraryTransactionRollback:
    """Test transaction rollback on errors."""
    
    @pytest.fixture
    def db_mock(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def service(self, db_mock):
        """Create a LibraryService instance."""
        return LibraryService(db_mock, user_id=1)
    
    def test_rollback_on_commit_error(self, service, db_mock, mock_document):
        """Test that rollback is called when commit fails."""
        from services.library.library_document_mixin import LibraryDocumentMixin
        
        mixin = LibraryDocumentMixin()
        mixin.db = db_mock
        
        db_mock.query.return_value.filter.return_value.first.return_value = mock_document
        db_mock.commit.side_effect = Exception("Database error")
        
        with pytest.raises(Exception):
            mixin.increment_views(1)
        
        db_mock.rollback.assert_called_once()
