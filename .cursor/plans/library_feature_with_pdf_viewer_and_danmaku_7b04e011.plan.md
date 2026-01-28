---
name: Library Feature with PDF Viewer and Danmaku
overview: Build a public library feature with simple Swiss design UI showing 4 PDF covers in a grid with book names. Users can click covers to view OCRed PDFs with lazy loading (only loads PDF metadata initially, renders pages on-demand), select text sentences and add danmaku/comments on selected text (with highlights visible to all users), like danmaku, and reply to danmaku comments. Uses pdfjs-dist + page-flip for magazine-style PDF viewing with page flip animations, and vue-danmaku for danmaku overlay. Text selections are highlighted on PDF pages, and clicking highlights shows all comments for that text.
todos:
  - id: backend-models
    content: Create database models (LibraryDocument, LibraryDanmaku with text selection support, LibraryDanmakuLike, LibraryDanmakuReply) in models/domain/library.py
    status: completed
  - id: backend-service
    content: Create LibraryService class in services/library/library_service.py for PDF upload, storage, and danmaku management
    status: completed
  - id: backend-router
    content: Create API router in routers/features/library.py with all endpoints (list, upload, view, danmaku CRUD, likes, replies)
    status: completed
  - id: feature-flag-backend
    content: Add FEATURE_LIBRARY flag to config/features_config.py and register router in main.py
    status: completed
  - id: frontend-store
    content: Create library Pinia store in frontend/src/stores/library.ts
    status: completed
  - id: frontend-api
    content: Add library API methods to frontend/src/utils/apiClient.ts
    status: completed
  - id: frontend-library-page
    content: Create LibraryPage.vue with simple Swiss design (4 cover images in grid, book names underneath, click to open PDF)
    status: completed
  - id: frontend-pdf-viewer
    content: Create PdfViewer.vue component using pdfjs-dist + page-flip for magazine-style page flip with lazy loading
    status: completed
  - id: frontend-danmaku
    content: Create DanmakuOverlay.vue component using vue-danmaku for positioned comments overlay, with text selection highlighting support
    status: completed
  - id: frontend-text-selection
    content: Implement text selection detection in PDF viewer, highlight rendering on canvas, and click handlers for highlights
    status: completed
  - id: frontend-comment-panel
    content: Create CommentPanel.vue for managing danmaku, likes, and threaded replies, with text selection mode support
    status: completed
  - id: frontend-viewer-page
    content: Create LibraryViewerPage.vue combining PDF viewer, danmaku overlay, and comment panel
    status: completed
  - id: frontend-router
    content: Add /library routes to frontend/src/router/index.ts
    status: completed
  - id: frontend-sidebar
    content: Add Library menu item to AppSidebar.vue with feature flag check
    status: completed
  - id: frontend-feature-flag
    content: Add featureLibrary to useFeatureFlags.ts and featureFlags store
    status: completed
  - id: install-dependencies
    content: Install pdfjs-dist, page-flip, and vue-danmaku packages in frontend
    status: completed
  - id: database-migration
    content: Database tables will be created automatically via init_db() when models are imported (handled by existing migration system)
    status: completed
  - id: backend-setup-pdfs
    content: Manually upload 4 PDFs to storage/library/ and cover images to storage/library/covers/, then add metadata to database (initial setup) - USER ACTION REQUIRED
    status: pending
  - id: backend-upload-endpoints
    content: Add POST/PUT/DELETE endpoints for PDF upload, metadata updates, and cover image upload (ready for future admin panel)
    status: completed
isProject: false
---

# Library Feature Implementation Plan

## Overview

Create a public library feature where users can view PDFs (managed manually in backend - 4 PDFs), add positioned danmaku/comments, like danmaku, and reply to comments. PDFs are loaded with lazy loading (only loads PDF metadata initially, renders pages on-demand).

## Architecture

### Backend Components

#### 1. Database Models (`models/domain/library.py`)

Create new domain models:

- **LibraryDocument**: PDF metadata (id, title, description, file_path, file_size, cover_image_path, uploader_id, views_count, likes_count, comments_count, created_at, updated_at, is_active)
- **LibraryDanmaku**: Positioned comments (id, document_id, user_id, page_number, position_x, position_y, content, color, created_at, updated_at, is_active)
  - **Text Selection Support** (for OCRed PDFs): 
    - selected_text (Text) - The actual text content that was selected
    - text_bbox (JSON) - Bounding box coordinates {x, y, width, height} relative to page
    - highlight_color (String) - Color for highlight rendering (optional, defaults based on comment count)
- **LibraryDanmakuLike**: Likes on danmaku (id, danmaku_id, user_id, created_at) with unique constraint
- **LibraryDanmakuReply**: Threaded replies (id, danmaku_id, user_id, parent_reply_id for nested replies, content, created_at, updated_at, is_active)

#### 2. API Router (`routers/features/library.py`)

Create FastAPI router with endpoints:

- `GET /api/library/documents` - List all PDFs (public, paginated)
- `GET /api/library/documents/{document_id}` - Get PDF details
- `GET /api/library/documents/{document_id}/file` - Serve PDF file (with access control)
- `POST /api/library/documents` - Upload PDF (admin only, multipart/form-data) - For future admin panel
- `PUT /api/library/documents/{document_id}` - Update PDF metadata (title, description) (admin only) - For future admin panel
- `POST /api/library/documents/{document_id}/cover` - Upload/update cover image (admin only, multipart/form-data) - For future admin panel
- `DELETE /api/library/documents/{document_id}` - Delete PDF (admin only) - For future admin panel
- `GET /api/library/documents/{document_id}/danmaku` - Get danmaku for PDF (optionally filtered by page or text selection)
- `POST /api/library/documents/{document_id}/danmaku` - Create danmaku comment
  - Supports text selection mode: {selected_text, text_bbox: {x, y, width, height}, page_number, content}
  - Supports position mode (fallback): {page_number, position_x, position_y, content}
- `POST /api/library/danmaku/{danmaku_id}/like` - Toggle like on danmaku
- `GET /api/library/danmaku/{danmaku_id}/replies` - Get replies to a danmaku
- `POST /api/library/danmaku/{danmaku_id}/replies` - Reply to a danmaku
- `DELETE /api/library/danmaku/{danmaku_id}` - Delete own danmaku
- `DELETE /api/library/danmaku/replies/{reply_id}` - Delete own reply

#### 3. Service Layer (`services/library/library_service.py`)

Create service class:

- `LibraryService`: Handles PDF upload, storage, danmaku management, like/reply operations
- Storage directory: `./storage/library/` (similar to knowledge space pattern)
- File validation: PDF only, max file size configurable

#### 4. Feature Flag (`config/features_config.py`)

Add `FEATURE_LIBRARY` property (disabled by default)

#### 5. Register Router (`routers/__init__.py` and `main.py`)

Import and register library router

### Frontend Components

#### 1. Library Page (`frontend/src/pages/LibraryPage.vue`)

Main library page with simple Swiss design:

- **Simple Grid Layout**:
  - Clean, minimal design following Swiss design principles
  - 4 cover images displayed in a grid (2x2 or 1x4 depending on screen size)
  - Book name displayed underneath each cover image
  - Clean typography, ample whitespace
  - Subtle hover effects (slight scale or shadow)
  - Click on cover image to open PDF viewer directly
- **Cover Images**:
  - Display cover images from `cover_image_path`
  - Aspect ratio maintained (book cover proportions)
  - Fallback placeholder if no cover image
- **Layout**:
  - Responsive grid: 2 columns on desktop, 1 column on mobile
  - Centered layout with max-width container
  - Clean spacing between items
- **Typography**:
  - Book title under each cover (clean, readable font)
  - Optional: View count or metadata in smaller text

#### 2. PDF Viewer Component (`frontend/src/components/library/PdfViewer.vue`)

PDF viewing component with magazine-style page flip and lazy loading:

- Uses `pdfjs-dist` (PDF.js) to render PDF pages directly to HTML5 canvas elements (no image conversion needed)
- Uses `page-flip` (StPageFlip) for realistic page turning animations
- Magazine-style reading experience with page flip effects
- **Text Selection & Highlighting**:
  - Enable text selection in PDF.js (text layer enabled for OCRed PDFs)
  - Detect user text selection (mouse drag or touch selection)
  - Show "Add Danmaku" button when text is selected
  - Store selected text content and bounding box coordinates
  - Render highlights on PDF pages for all text selections with danmaku
  - Click handler on highlights to show all danmaku for that text selection
  - Highlight color indicates number of comments (e.g., darker = more comments)
- **Lazy Loading Implementation**:
  - Initial: Load only PDF metadata/structure (not all pages)
  - Pre-render: First 2-3 pages rendered immediately
  - On-demand: Render pages as user approaches them (current ±2 pages)
  - Memory efficient: Unload pages >5 pages away from current position
  - Uses page-flip events to trigger rendering of adjacent pages
- Custom navigation controls (prev/next page buttons, page number display)
- Zoom controls (zoom in/out, fit to width/page)
- Fullscreen mode
- Touch/drag support for mobile devices
- Loading indicators for pages being rendered

#### 3. Danmaku Overlay (`frontend/src/components/library/DanmakuOverlay.vue`)

Danmaku display component:

- Uses `vue-danmaku` for danmaku/bullet screen animations
- Fetches danmaku for current visible page(s)
- Displays positioned danmaku at specified coordinates (page_number, position_x, position_y)
- **Text Selection Highlights**:
  - Renders highlights on PDF canvas for text selections with danmaku
  - Highlight color/intensity based on number of comments
  - Click handler on highlights to show comment panel for that text selection
  - Highlights persist across page flips
- Overlays on top of PDF pages during page flip animations
- Real-time updates (polling initially, can upgrade to WebSocket later)

#### 4. Comment Panel (`frontend/src/components/library/CommentPanel.vue`)

Side panel for comments:

- List of danmaku/comments for current page or selected text
- **Text Selection Mode**:
  - When user selects text, show "Add Comment" button
  - When user clicks highlighted text, show all danmaku for that text selection
  - Display selected text snippet at top of panel
  - Filter danmaku by text selection (show only comments on that text)
- **Position Mode** (fallback):
  - Add new danmaku with position picker (for non-text comments)
- Like/unlike danmaku
- View replies to danmaku
- Reply to danmaku (threaded)
- Delete own comments

#### 5. Library Store (`frontend/src/stores/library.ts`)

Pinia store for library state:

- PDF list management
- Current PDF state
- Danmaku state
- API methods

#### 6. API Client Methods (`frontend/src/utils/apiClient.ts`)

Add library API methods:

- `getLibraryDocuments()` - List all PDFs
- `getLibraryDocument(id)` - Get PDF metadata
- `getLibraryDocumentFile(id)` - Get PDF file URL for viewing
- `uploadLibraryDocument(file)` - Upload PDF (for future admin panel)
- `updateLibraryDocument(id, data)` - Update PDF metadata (for future admin panel)
- `uploadLibraryDocumentCover(id, imageFile)` - Upload/update cover image (for future admin panel)
- `deleteLibraryDocument(id)` - Delete PDF (for future admin panel)
- `getDanmaku(documentId, page?, selectedText?)` - Get danmaku for PDF/page/text selection
- `createDanmaku(documentId, data)` - Create danmaku comment (supports text selection data: selectedText, textBbox, pageNumber)
- `likeDanmaku(danmakuId)` - Toggle like on danmaku
- `getDanmakuReplies(danmakuId)` - Get replies to danmaku
- `replyToDanmaku(danmakuId, content, parentReplyId?)` - Reply to danmaku

#### 7. Router Configuration (`frontend/src/router/index.ts`)

Add route:

- `/library` - LibraryPage
- `/library/:id` - PDF viewer page

#### 8. Sidebar Integration (`frontend/src/components/sidebar/AppSidebar.vue`)

Add menu item:

- Library menu item (with feature flag check)
- Icon: Book or Library icon

#### 9. Feature Flag Composable (`frontend/src/composables/useFeatureFlags.ts`)

Add `featureLibrary` computed property

#### 10. Feature Flag Store (`frontend/src/stores/featureFlags.ts`)

Add `feature_library` flag handling

#### 11. Backend PDF Management

**Initial Setup (Manual):**

- Upload 4 PDFs manually to `./storage/library/` directory
- Upload cover images manually to `./storage/library/covers/` directory
- Add PDF metadata (title, description, cover_image_path) directly to database via SQL or admin script

**Future Admin Panel (Endpoints Ready):**

- Upload/update/delete endpoints are implemented and ready
- Admin panel UI will be built later to use these endpoints

### Dependencies

#### Frontend (`frontend/package.json`)

Add packages:

- `pdfjs-dist` - PDF.js library for rendering PDF pages (actively maintained by Mozilla)
- `page-flip` - StPageFlip library for realistic page flip animations (actively maintained, MIT license)
- `vue-danmaku` - Vue 3 danmaku/bullet screen component for overlay comments

#### Backend

No new dependencies needed (uses existing FastAPI, SQLAlchemy patterns)

### File Structure

```
Backend:
- models/domain/library.py (new)
- routers/features/library.py (new)
- services/library/library_service.py (new)
- services/library/__init__.py (new)

Frontend:
- frontend/src/pages/LibraryPage.vue (new)
- frontend/src/pages/LibraryViewerPage.vue (new)
- frontend/src/components/library/PdfViewer.vue (new)
- frontend/src/components/library/DanmakuOverlay.vue (new)
- frontend/src/components/library/CommentPanel.vue (new)
- frontend/src/stores/library.ts (new)
```

### Implementation Steps

1. **Backend Models & Database**
  - Create `library.py` domain models
  - Add to `models/domain/__init__.py`
  - Create migration script
2. **Backend Service Layer**
  - Create `LibraryService` class
  - Implement danmaku CRUD operations
  - Implement PDF upload/storage logic (for future admin panel use)
3. **Backend API Router**
  - Create router with all endpoints (read + write)
  - Add authentication/admin checks for write endpoints
  - Add file serving endpoint
  - Upload/update/delete endpoints ready for future admin panel
4. **Feature Flag Setup**
  - Add `FEATURE_LIBRARY` to backend config
  - Add to frontend feature flags
5. **Frontend Store & API**
  - Create library store
  - Add API client methods
6. **Frontend Components**
  - Create LibraryPage with bookshelf UI
  - Create Bookshelf component (3D shelf container)
  - Create BookSpine component (individual book on shelf)
  - Create PDF viewer component (integrate PDF.js + page-flip)
  - Create danmaku overlay (integrate vue-danmaku)
  - Create comment panel
  - Implementation approach:
    - Library Page: Simple grid layout with cover images and titles, clean Swiss design
    - PDF Viewer: Use PDF.js to load and render PDF pages to canvas (enable text layer for OCRed PDFs)
  - Use canvas elements directly (no image conversion)
  - Initialize page-flip with rendered pages for flip animation
  - Implement text selection detection and highlight rendering
  - Overlay vue-danmaku component on top of pages
  - Handle page flip events to update danmaku for visible pages
  - Render highlights on canvas overlay for text selections with danmaku
7. **Frontend Integration**
  - Add router routes
  - Add sidebar menu item
  - Wire up feature flags
8. **Backend PDF Setup**
  - Manually upload 4 PDFs to `./storage/library/` directory
  - Manually upload cover images to `./storage/library/covers/` directory  
  - Add PDF metadata to database via SQL INSERT or admin script
  - Verify file paths and cover image paths are correct
9. **Testing & Polish**
  - Test library page UI (cover images, click navigation)
  - Test PDF viewing (lazy loading)
  - Test text selection and highlighting
  - Test danmaku creation from text selection
  - Test clicking highlights to view comments
  - Test danmaku positioning (fallback mode)
  - Test likes and replies
  - Test page flip animations
  - Test highlight rendering across page flips

### Key Implementation Details

- **PDF Storage**: Store in `./storage/library/` with filename pattern `{document_id}_{original_filename}.pdf`
- **Cover Image Storage**: Store in `./storage/library/covers/` with filename pattern `{document_id}_cover.{ext}` (supports JPG, PNG, WEBP)
- **PDF Rendering**: Use PDF.js to render pages directly to HTML5 canvas elements (no image conversion)
- **Page Flip Integration**: Each PDF page rendered as canvas element, wrapped in page-flip container using `CanvasRender` mode
- **No Image Conversion**: Canvas elements used directly - better performance, less memory overhead than converting to images
- **Danmaku Positioning**: 
  - **Text Selection Mode** (primary): Store selected_text, text_bbox (bounding box: x, y, width, height), page_number
  - **Position Mode** (fallback): Store page_number (1-indexed) and position_x, position_y (0-100 percentage or pixel coordinates relative to page)
  - Highlight rendering: Use text_bbox to draw highlight rectangles on PDF canvas
- **Lazy Loading Strategy**:
  - Initial load: Only load PDF document structure/metadata (via PDF.js `getDocument()`)
  - Pre-render: Render first 2-3 pages immediately (cover + first page)
  - On-demand rendering: Render pages as user approaches them (e.g., when flipping to page 5, render pages 4-6 in background)
  - Page-flip events: Use page-flip `onFlip` callback to trigger rendering of next/previous pages
  - Danmaku: Fetch danmaku only for currently visible pages (not all pages at once)
  - Memory management: Unload/render pages that are far from current position to save memory
- **Permissions**: Public read for PDFs; admin-only write for PDFs; all users can create danmaku/replies
- **PDF Management**: Initial setup done manually (upload files, add DB records). Upload/update/delete endpoints ready for future admin panel UI
- **File Serving**: Use FastAPI FileResponse with proper headers for PDF serving
- **Real-time Updates**: Use polling initially (can upgrade to WebSocket later)

### Similar Patterns to Follow

- **School Zone** (`routers/features/school_zone.py`) - for like/comment patterns
- **Knowledge Space** (`services/knowledge/knowledge_space_service.py`) - for file upload/storage patterns
- **Course Page** (`frontend/src/pages/CoursePage.vue`) - for grid/list UI patterns (reference, but bookshelf is different)

### Library Page UI Design (Swiss Design)

**Visual Design:**

- Clean, minimal Swiss design principles
- Simple grid layout (2x2 on desktop, 1x4 on mobile)
- Cover images displayed prominently
- Book names underneath covers (clean typography)
- Ample whitespace, clean spacing
- Subtle hover effects (slight scale or shadow)
- Click on cover image navigates to PDF viewer

**Layout:**

- Centered container with max-width
- Responsive grid: 2 columns desktop, 1 column mobile
- Cover images maintain aspect ratio
- Clean typography for book titles
- Optional: View count or metadata in smaller text

**Implementation:**

- Use CSS Grid or Flexbox for simple layout
- Cover images from `cover_image_path` field
- Fallback placeholder if no cover image
- Click handler navigates to `/library/:id` route

### Library Integration Details

**PDF.js + page-flip Integration (Lazy Loading):**

**When user clicks PDF:**

1. **Initial Load (Fast)**: Use PDF.js `getDocument(url)` to load PDF structure/metadata only
  - This loads the PDF index/outline (very lightweight, ~few KB)
  - Does NOT load any page content yet
  - Returns total page count immediately
2. **Pre-render First Pages**: Render first 2-3 pages to canvas using `pdf.getPage(pageNum).then(page => page.render({ canvasContext }))`
  - PDF.js renders directly to HTML5 canvas elements (no image conversion needed)
  - Cover page (page 1)
  - First content page (page 2)
  - Optional: Page 3 for smooth initial flip
  - Canvas elements are memory-efficient and can be used directly
3. **Initialize page-flip**: Start with pre-rendered canvas elements, use placeholder divs with loading indicators for unrendered pages
  - StPageFlip supports canvas rendering via `CanvasRender` mode
  - No need to convert canvas to images - use canvas elements directly

**As user flips pages:**
4. **On-demand Rendering**: 

- Listen to page-flip `onFlip` event to detect page changes
- When user flips to page N, check if pages N-1, N, N+1 are rendered
- If not rendered, queue rendering jobs: `pdf.getPage(pageNum).then(page => page.render({ canvasContext }))`
- Replace placeholder divs with rendered canvas elements when ready
- Show loading spinner on placeholder pages
- **No image conversion**: Use canvas elements directly (better performance, less memory)

1. **Memory Management**:
  - Keep rendered canvas elements in memory for current ±3 pages (e.g., if on page 5, keep pages 2-8)
  - Unload pages that are >5 pages away from current position (remove canvas elements from DOM, free memory)
  - Re-render when user navigates back to unloaded pages (canvas elements are lightweight to recreate)
2. **Danmaku Loading**: Fetch danmaku only for currently visible page(s) via API call on page flip
  - Don't fetch all danmaku for entire PDF at once
  - Fetch on page change event

**Performance Benefits:**

- Initial load: Only PDF metadata (~few KB) instead of entire PDF (could be 10-100MB)
- Progressive rendering: Pages load as needed, not all at once
- Memory efficient: Only keep nearby pages in memory
- Fast navigation: Pre-render adjacent pages before user reaches them

**Vue-danmaku Integration:**

1. Initialize danmaku component overlay on PDF viewer
2. Fetch danmaku data for current page from API
3. Position danmaku based on stored coordinates
4. Update danmaku when page changes
5. Handle user interactions (click to reply, like, etc.)

**Text Selection & Highlighting Integration:**

1. **Text Selection Detection**:
  - Enable PDF.js text layer for OCRed PDFs
  - Listen to text selection events (mouseup, touchend)
  - Get selected text content using `window.getSelection()` or PDF.js text layer API
  - Calculate bounding box of selected text using text layer coordinates
  - Show "Add Danmaku" button near selection
2. **Highlight Rendering**:
  - Fetch all danmaku with text selections for current page
  - Group danmaku by selected_text (same text = same highlight)
  - Render highlight rectangles on PDF canvas overlay using text_bbox coordinates
  - Use highlight color/intensity based on comment count (darker = more comments)
  - Make highlights clickable (show all danmaku for that text when clicked)
3. **Comment Creation**:
  - When user clicks "Add Danmaku" after text selection:
    - Store selected_text, text_bbox (x, y, width, height), page_number
    - Open comment panel with selected text displayed
    - User types comment and submits
    - API creates danmaku with text selection data
    - Highlight appears on PDF page
4. **Comment Viewing**:
  - When user clicks highlighted text:
    - Fetch all danmaku for that text selection (match by selected_text and text_bbox)
    - Show comment panel with filtered danmaku
    - Display selected text snippet at top

