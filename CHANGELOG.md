# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.16.0] - 2026-01-30

### Added
- **Library Sync Validation**: Added comprehensive sync validation system (`sync_validator.py`) to maintain consistency between PDF files in storage, cover images, and database records. Includes validation functions and sync reporting capabilities.
- **PDF Analysis Scripts**: Added two new analysis scripts (`analyze_pdf_files.py` and `analyze_pdf_lazy_loading.py`) for analyzing PDF structure and verifying lazy loading feasibility.
- **Library API Enhancements**: Enhanced library router with additional endpoints and improved functionality for library management.

### Changed
- **PDF Viewer Component**: Significant improvements to PDF viewer component with enhanced functionality (260+ lines added).
- **Auto Import Scheduler**: Updated auto import scheduler with improved error handling and validation logic.
- **Library Service**: Enhanced library service with additional methods and improved data handling.
- **Application Lifespan**: Updated application lifecycle management to integrate new library sync validation features.

## [5.15.1] - 2026-01-29

### Fixed
- **PDF Viewer Pin Interaction**: Fixed critical issue where PDF library pins were rendered correctly but not clickable or draggable. The root cause was that pin elements inherited `pointer-events: none` from the parent `.pdf-pins-layer`. Fixed by explicitly setting `pointer-events: auto` inline on pin elements at multiple points in the lifecycle (creation, Vue mounting, DOM appending) and adding `!important` to the CSS rule as a safeguard.
- **PDF Viewer Ref Safety**: Added comprehensive null checks for `pinsLayerRef` and `canvasRef` throughout the component to prevent errors when refs are not yet available, improving stability during component lifecycle transitions.

## [5.15.0] - Previous Release

Initial version tracking.
