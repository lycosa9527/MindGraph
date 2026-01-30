---
name: PDF to Image Viewer Transition
overview: Transition the library system from PDF.js-based PDF viewing to image-based viewing. Images will be manually exported to folders (one folder per book), and the system will be updated to serve and display these images.
todos:
  - id: update-db-model
    content: Add use_images, pages_dir_path, total_pages fields to LibraryDocument model
    status: completed
  - id: create-api-endpoint
    content: Create GET /api/library/documents/{id}/pages/{page} endpoint to serve page images
    status: completed
  - id: create-image-viewer
    content: Create ImageViewer.vue component for displaying page images
    status: completed
  - id: update-viewer-page
    content: Update LibraryViewerPage.vue to support both PDF and image modes
    status: completed
  - id: create-registration-script
    content: Create register_image_folders.py script to scan and register existing image folders
    status: completed
  - id: update-api-client
    content: Update apiClient.ts with image URL helpers and type definitions
    status: completed
isProject: false
---

# PDF to Image Viewer Transition Plan

## Overview

Transition the library system from PDF.js-based viewing to image-based viewing. Images will be manually exported by the user (one folder per book containing JPEG/PNG images), and the system will be updated to detect, serve, and display these images.

## Architecture Changes

### 1. Manual Image Organization

**User Responsibility:**

- User manually exports PDFs to images (JPEG or PNG format) - handled outside this system
- Each book gets its own folder containing page images
- Images should be named sequentially (e.g., `page_001.jpg`, `page_002.jpg`, `001.jpg`, `002.jpg`, etc.)
- Folders are placed directly under `storage/library/` (alongside PDFs and covers folder)

**Supported Naming Patterns:**

- `page_001.jpg`, `page_002.jpg`, ... (with leading zeros)
- `001.jpg`, `002.jpg`, ... (with leading zeros)
- `page1.jpg`, `page2.jpg`, ... (without leading zeros)
- `1.jpg`, `2.jpg`, ... (without leading zeros)
- Any sequential numeric pattern

### 2. Database Schema Updates

**File: `models/domain/library.py**`

Add to `LibraryDocument` model:

- `use_images` (Boolean, default=False) - Flag indicating if document uses images instead of PDF
- `pages_dir_path` (String, nullable=True) - Path to directory containing page images
- `total_pages` (Integer, nullable=True) - Total number of pages (for image-based docs)

**PostgreSQL Migration:**

- The system uses automatic migration (`utils/migration/db_migration.py`)
- Migration automatically detects missing columns and adds them
- Run `python scripts/db/run_migrations.py` to apply schema changes
- Or restart application - migrations run automatically on startup

**Database Reset (Dev Environment):**

Since we're on dev machine, we can clear library-related tables and start fresh:

- Clear `library_documents` table
- Clear `library_danmaku` table (cascade delete)
- Clear `library_danmaku_likes` table (cascade delete)
- Clear `library_danmaku_replies` table (cascade delete)
- Clear `library_bookmarks` table (cascade delete)
- Then re-import documents (PDFs and/or image folders)

**Migration Considerations:**

- New documents can be set to `use_images=True` when image folder is registered
- Registration script will scan existing image folders and update database records
- All existing queries continue to work (new fields are nullable)
- After reset, import process will create fresh records with new schema

### 3. Backend API Changes

**File: `routers/features/library.py**`

**New Endpoint:**

- `GET /api/library/documents/{document_id}/pages/{page_number}` - Serve page image
  - Returns image file with proper Content-Type
  - Supports caching headers
  - Handles missing pages gracefully

**Updated Endpoint:**

- `GET /api/library/documents/{document_id}` - Include `use_images`, `total_pages`, `pages_dir_path` in response
- `GET /api/library/documents/{document_id}/file` - Keep for backward compatibility (PDF serving)

**File: `services/library/library_service.py**`

- Update `get_document()` to include image-related fields
- Add helper methods for image path resolution

### 4. Frontend Component Updates

**New File: `frontend/src/components/library/ImageViewer.vue**`

- Similar structure to `PdfViewer.vue` but displays images instead
- Load images on-demand (lazy loading)
- Support zoom, rotation, navigation
- Handle danmaku/pins overlay (same coordinate system)
- Preload adjacent pages for smooth navigation

**Key Features:**

- Image loading with loading states
- Zoom controls (fit-width, fit-page, custom zoom)
- Page navigation (previous/next)
- Pin/danmaku overlay (reuse existing `DanmakuOverlay` component)
- Responsive image display

**File: `frontend/src/pages/LibraryViewerPage.vue**`

- Detect `use_images` flag from document
- Conditionally render `ImageViewer` or `PdfViewer` based on flag
- Update `pdfUrl` computed to handle image-based documents

**File: `frontend/src/utils/apiClient.ts**`

- Add `getLibraryDocumentPageImageUrl(documentId, pageNumber)` function
- Update document type definitions to include image fields

### 5. Update Import Library Module

**File: `services/library/pdf_importer.py**`

Update import functions to also detect and register image folders:

- `**import_pdfs_from_folder()**` - After importing PDF, check if corresponding image folder exists
  - If image folder found, register it automatically
  - Set `use_images=True`, `pages_dir_path`, and `total_pages`
  - Prefer images over PDF if both exist (or make configurable)
- `**auto_import_new_pdfs()**` - Same logic for auto-import
  - Scan for both PDFs and image folders
  - Create documents for image folders even if PDF doesn't exist
  - Match folders to documents intelligently

**New Helper Functions:**

- `detect_image_folder_for_pdf(pdf_path, library_dir)` - Check if image folder exists for PDF
- `register_image_folder_for_document(db, document_id, folder_path)` - Register folder for document
- `import_image_folder(db, folder_path, library_dir, uploader_id)` - Import image folder as new document

**File: `scripts/library_import.py**`

- Update CLI script to support image folder detection
- Add `--detect-images` flag to automatically detect and register image folders
- Add `--images-only` mode to import only image folders (skip PDFs)

### 6. Image Folder Registration Script

**New File: `scripts/register_image_folders.py**`

- Scan `storage/library/` directory for image folders (ignore PDFs and `covers/` folder)
- Match folders to existing documents (by folder name or document ID)
- Detect image files and count total pages
- Update database records with `use_images=True`, `pages_dir_path`, and `total_pages`
- Support manual folder-to-document mapping
- Handle errors and provide progress reporting
- Support dry-run mode

**Key Functions:**

- `scan_image_folders(library_dir)` - Find all folders containing images
- `detect_page_images(folder_path)` - Detect and sort image files in folder
- `count_pages(folder_path)` - Count total pages from images
- `register_folder(document_id, folder_path)` - Update database record

**Usage:**

```bash
python scripts/register_image_folders.py  # Scan storage/library/ and register all image folders
python scripts/register_image_folders.py --document-id 6 --folder book_folder_name  # Register specific folder
python scripts/register_image_folders.py --dry-run  # Preview without updating database
```

**Folder Detection Logic:**

- Scan `storage/library/` for directories
- Skip `covers/` directory (used for cover images, not page images)
- Skip files (like `.pdf` files)
- For each directory, check if it contains image files (.jpg, .jpeg, .png)
- Match folder to document by name similarity or manual mapping
- `covers/` folder is preserved and continues to store cover/thumbnail images

### 7. Clear Library Tables Script (Dev Environment)

**New File: `scripts/clear_library_tables.py**`

- Clear all library-related tables in PostgreSQL for fresh start
- Handles CASCADE deletes properly (respects foreign key constraints)
- Confirms action before proceeding (safety check)
- Supports dry-run mode

**Tables to Clear (in order due to foreign keys):**

- `library_danmaku_replies` (references library_danmaku)
- `library_danmaku_likes` (references library_danmaku)
- `library_danmaku` (references library_documents)
- `library_bookmarks` (references library_documents)
- `library_documents` (parent table)

**Usage:**

```bash
python scripts/clear_library_tables.py  # Clear all tables (with confirmation)
python scripts/clear_library_tables.py --yes  # Skip confirmation
python scripts/clear_library_tables.py --dry-run  # Preview what would be deleted
```

**Safety Features:**

- Requires confirmation unless `--yes` flag is used
- Shows count of records that will be deleted
- Dry-run mode to preview without actually deleting
- Only works in dev environment (checks environment variable or config)

### 8. Storage Structure

**Directory Structure (User-Managed):**

```
storage/library/
  ├── book1/ (folder with page images - user-created)
  │   ├── page_001.jpg
  │   ├── page_002.jpg
  │   ├── page_003.jpg
  │   └── ...
  ├── book2/ (folder with page images - user-created)
  │   ├── 001.jpg
  │   ├── 002.jpg
  │   └── ...
  ├── *.pdf (existing PDFs)
  └── covers/ (cover images - existing, still used)
      ├── {document_id}_cover.jpg
      └── ...
```

**Notes:**

- Book folders (containing page images) are placed directly under `storage/library/`
- `covers/` folder remains for cover/thumbnail images (one per document)
- Folder names can match document titles, IDs, or be user-defined
- Registration script will scan `storage/library/` and match folders to documents
- Script will ignore `.pdf` files and `covers/` directory when scanning for book folders
- Images can be JPEG (.jpg, .jpeg) or PNG (.png)
- Page images should be numbered sequentially (any pattern supported)
- Cover images continue to work as before (stored in `covers/` folder)

### 9. Image Path Resolution Service

**New File: `services/library/image_path_resolver.py**`

- Resolve page image paths from folder path and page number
- Support multiple image naming patterns
- Handle missing images gracefully
- Detect image format (JPEG/PNG) automatically

**Key Functions:**

- `resolve_page_image(folder_path, page_number)` - Get image path for specific page
- `detect_image_pattern(folder_path)` - Detect naming pattern in folder
- `list_page_images(folder_path)` - List all page images sorted by page number

## Implementation Steps

1. **Update Database Model**
  - Add new fields (`use_images`, `pages_dir_path`, `total_pages`) to `LibraryDocument` model
  - Run database migration: `python scripts/db/run_migrations.py`
  - Verify columns are added correctly in PostgreSQL

1a. **Clear Library Tables (Dev Environment)**

- Create `scripts/clear_library_tables.py` script
- Clear all library-related tables (with CASCADE handling)
- Verify tables are empty
- This allows fresh start with new schema

1. **Create Image Path Resolution Service**
  - Implement `image_path_resolver.py` to handle various naming patterns
  - Test with sample folders containing different naming conventions
2. **Update Import Library Module**
  - Update `import_pdfs_from_folder()` to detect and register image folders
  - Update `auto_import_new_pdfs()` to handle image folders
  - Add helper functions for image folder detection and registration
  - Test import with both PDFs and image folders
3. **Update Library Service**
  - Update `get_document()` and queries to include image-related fields
  - Add image path resolution helpers
  - Ensure backward compatibility
4. **Create Backend API Endpoints**
  - Implement page image serving endpoint
  - Update document endpoint to include image fields
  - Test API endpoints
5. **Create Image Viewer Component**
  - Build `ImageViewer.vue` component
  - Implement zoom, navigation, loading states
  - Test with sample images
6. **Update Frontend Integration**
  - Modify `LibraryViewerPage.vue` to support both modes
  - Update API client
  - Test end-to-end flow
7. **Create Registration Script**
  - Build folder scanning and registration script
  - Test with sample image folders
  - Support manual folder-to-document mapping
8. **Testing & Validation**
  - Test image viewer with all features (zoom, pins, danmaku)
  - Verify danmaku coordinates work correctly
  - Test performance with large documents
  - Verify backward compatibility (PDF mode still works)

## Files to Create/Modify

### New Files:

- `services/library/image_path_resolver.py` - Image path resolution service (handles various naming patterns)
- `frontend/src/components/library/ImageViewer.vue` - Image viewer component
- `scripts/register_image_folders.py` - Folder registration script (scans and registers existing image folders)
- `scripts/clear_library_tables.py` - Script to clear library tables in PostgreSQL (dev environment)

### Modified Files:

- `models/domain/library.py` - Add image-related fields to `LibraryDocument`
- `routers/features/library.py` - Add page image endpoint, update document endpoint
- `services/library/library_service.py` - Add image path helpers
- `frontend/src/pages/LibraryViewerPage.vue` - Support both PDF and image modes (minimal changes - just conditional rendering)
- `frontend/src/utils/apiClient.ts` - Add image URL helper, update types

### Unchanged Files (Reused As-Is):

- `frontend/src/components/library/PdfToolbar.vue` - **NO CHANGES** - works with both viewers
- `frontend/src/components/library/DanmakuOverlay.vue` - **NO CHANGES** - works with both viewers
- `frontend/src/components/library/CommentPanel.vue` - **NO CHANGES** - works with both viewers

## Considerations

- **Storage Space**: Images will take more space than PDFs (user controls quality/size)
- **Performance**: Image loading should be faster than PDF.js parsing
- **Image Quality**: User controls export quality and format (handled outside system)
- **Backward Compatibility**: Keep PDF mode working for existing documents
- **Danmaku Coordinates**: Image coordinates should match PDF coordinates (may need scaling)
- **Error Handling**: Handle missing images, corrupted files, wrong folder structure gracefully
- **Folder Matching**: Need flexible matching between image folders and documents (by name, ID, or manual mapping)
- **Image Naming**: Support various naming patterns (with/without leading zeros, different prefixes)

## Testing Checklist

- Test image path resolution with various naming patterns
- Test page image serving endpoint
- Test image viewer component (zoom, navigation)
- Test danmaku/pins with images
- Test folder registration script with sample folders
- Test folder-to-document matching logic
- Verify backward compatibility (PDF mode)
- Performance testing (loading speed, memory usage)
- Test error handling (missing images, wrong page numbers)

