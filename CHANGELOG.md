# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.16.0] - 2026-01-30

### Added
- **Library Feature**: Complete library management system with PDF viewer, danmaku (comment overlay), and document management capabilities. Includes full frontend and backend implementation with Vue components, Pinia stores, and FastAPI endpoints.
- **PDF Viewer Component**: Interactive PDF viewer with zoom, navigation, page rendering, and pin/comment overlay support using PDF.js.
- **Danmaku/Comment System**: Real-time comment overlay system for PDF documents with pin-based annotations and comment panels.
- **Library Sync Validation**: Comprehensive sync validation system (`sync_validator.py`) to maintain consistency between PDF files in storage, cover images, and database records. Includes validation functions and sync reporting capabilities.
- **PDF Analysis Scripts**: Added analysis scripts (`analyze_pdf_files.py` and `analyze_pdf_lazy_loading.py`) for analyzing PDF structure and verifying lazy loading feasibility.
- **PDF Utilities Module**: New `pdf_utils.py` module with PDF validation (magic bytes check) and path normalization utilities for cross-platform compatibility.
- **Auto Import Scheduler**: Background automatic PDF import system with startup initialization and periodic background scheduler (`auto_import_scheduler.py`).
- **Library Service**: Complete library service implementation with document management, PDF import, cover extraction, and database operations.
- **Feature Flags System**: Frontend feature flag system for enabling/disabling library features via configuration.
- **API Client Utilities**: Comprehensive API client utilities for frontend-backend communication with error handling and type safety.
- **PDF Cover Extraction**: Automatic cover image extraction from PDF documents with standardized naming (`{document_id}_cover.png`).
- **Diagnostic Endpoints**: Added `/._diagnostic/static-files` endpoint for verifying static file serving configuration.

### Changed
- **PDF Viewer Component**: Significant improvements to PDF viewer component with enhanced functionality (260+ lines added in latest update, 300+ lines in initial implementation).
- **PDF Worker Loading**: Refactored PDF.js worker loading to use `/pdfjs/` directory with StaticFiles mount, consistent with other static file serving patterns.
- **Library Router**: Enhanced library router with comprehensive endpoints for document management, PDF serving, cover images, and library operations.
- **Path Normalization**: Implemented path normalization across all library modules for cross-platform compatibility (WSL/Ubuntu/Windows).
- **Cover Image Handling**: Improved cover image loading with fallback to placeholder icons when images fail to load, removed strict v-if checks.
- **PDF Path Resolution**: Enhanced PDF path resolution with fallback logic (absolute path → storage_dir → CWD) for cross-platform compatibility.
- **Error Handling**: Improved error handling throughout library modules with specific exception types and detailed logging.
- **Duplicate Detection**: Enhanced duplicate detection with normalized path comparison.
- **Auto Import Scheduler**: Updated auto import scheduler with improved error handling and validation logic.
- **Application Lifespan**: Updated application lifecycle management to integrate library auto-import and sync validation features.
- **Static File Serving**: Enhanced static file serving with improved logging and diagnostic capabilities.

### Fixed
- **PDF Viewer Pin Interaction**: Fixed critical issue where PDF library pins were rendered correctly but not clickable or draggable. Root cause was pin elements inheriting `pointer-events: none` from parent layer. Fixed by explicitly setting `pointer-events: auto` inline at multiple lifecycle points.
- **PDF Viewer Worker Loading**: Fixed 404 errors when loading PDF.js worker in production by serving root-level static files from dist/ and adding proper StaticFiles mounts.
- **PDF Viewer Ref Safety**: Added comprehensive null checks for `pinsLayerRef` and `canvasRef` throughout component to prevent errors when refs are not yet available.
- **Library Cover Images**: Fixed issue where cover images didn't show even when files existed by removing strict v-if checks and adding proper error handling.
- **PDF Path Resolution**: Fixed PDF loading issues due to path differences between WSL and Ubuntu environments with improved fallback logic.
- **TypeScript Errors**: Fixed TypeScript errors in PDF viewer components.
- **Linter Errors**: Removed unused `library_auto_import_task` variable from application lifespan module to resolve linter warnings.
- **Danmaku Pin Rendering**: Fixed danmaku pin rendering and click handling in PDF viewer.
- **Library Page Linting**: Fixed linting errors in LibraryPage.vue component.

## [5.15.1] - 2026-01-29

### Fixed
- **PDF Viewer Pin Interaction**: Fixed critical issue where PDF library pins were rendered correctly but not clickable or draggable. The root cause was that pin elements inherited `pointer-events: none` from the parent `.pdf-pins-layer`. Fixed by explicitly setting `pointer-events: auto` inline on pin elements at multiple points in the lifecycle (creation, Vue mounting, DOM appending) and adding `!important` to the CSS rule as a safeguard.
- **PDF Viewer Ref Safety**: Added comprehensive null checks for `pinsLayerRef` and `canvasRef` throughout the component to prevent errors when refs are not yet available, improving stability during component lifecycle transitions.

## [5.15.0] - Previous Release

Initial version tracking.
