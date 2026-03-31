/**
 * API Client with Automatic Token Refresh
 *
 * This module provides a centralized API client that:
 * - Automatically refreshes expired access tokens using refresh tokens
 * - Retries failed requests after token refresh
 * - Handles session expiration gracefully
 * - Uses httpOnly cookies for token storage (no localStorage)
 *
 * Security:
 * - Tokens stored in httpOnly cookies (not accessible to JavaScript)
 * - Refresh tokens have restricted path (/api/auth)
 * - Device binding prevents token theft across devices
 */
import { useAuthStore } from '@/stores/auth'

const API_BASE = '/api'

// Track if a refresh is in progress to prevent multiple simultaneous refreshes
let isRefreshing = false
let refreshPromise: Promise<boolean> | null = null

/**
 * Attempt to refresh the access token using the refresh token cookie
 * Returns true if refresh successful, false otherwise
 */
async function refreshAccessToken(): Promise<boolean> {
  // If already refreshing, wait for the existing refresh to complete
  if (isRefreshing && refreshPromise) {
    return refreshPromise
  }

  isRefreshing = true
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'same-origin', // Include cookies
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (response.ok) {
        return true
      }

      return false
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error('[ApiClient] Token refresh error:', error)
      }
      return false
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()

  return refreshPromise
}

/**
 * Make an API request with automatic token refresh
 *
 * @param endpoint - API endpoint (with or without leading slash)
 * @param options - Fetch options
 * @returns Promise<Response>
 */
export async function apiRequest(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const url = endpoint.startsWith('/') ? endpoint : `${API_BASE}/${endpoint}`

  // Prepare headers
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  // Make the initial request
  let response = await fetch(url, {
    ...options,
    headers,
    credentials: 'same-origin', // Include cookies
  })

  // If unauthorized, attempt token refresh and retry
  if (response.status === 401) {
    // Don't retry refresh endpoint to avoid infinite loop
    if (endpoint.includes('/auth/refresh')) {
      return response
    }

    const authStore = useAuthStore()
    // Check if user was previously authenticated (before refresh attempt)
    const hadUserBeforeRefresh = !!authStore.user || !!sessionStorage.getItem('auth_user')

    const refreshed = await refreshAccessToken()

    if (refreshed) {
      response = await fetch(url, {
        ...options,
        headers,
        credentials: 'same-origin',
      })
    } else {
      // Refresh failed - only show session expired modal if user was previously authenticated
      // If user was never authenticated, just return the 401 response (for public endpoints)
      if (hadUserBeforeRefresh) {
        // Pass null to stay on current page (no redirect)
        authStore.handleTokenExpired('Your session has expired. Please log in again.', undefined)
      } else {
        // User was never authenticated - return 401 without showing modal
        // This allows public endpoints to handle 401 gracefully
      }
    }
  }

  return response
}

/**
 * Make an authenticated GET request
 */
export async function apiGet(endpoint: string, options: RequestInit = {}): Promise<Response> {
  return apiRequest(endpoint, { ...options, method: 'GET' })
}

/**
 * Make an authenticated POST request
 */
export async function apiPost(
  endpoint: string,
  body?: unknown,
  options: RequestInit = {}
): Promise<Response> {
  return apiRequest(endpoint, {
    ...options,
    method: 'POST',
    body: body ? JSON.stringify(body) : undefined,
  })
}

/**
 * Make an authenticated PUT request
 */
export async function apiPut(
  endpoint: string,
  body?: unknown,
  options: RequestInit = {}
): Promise<Response> {
  return apiRequest(endpoint, {
    ...options,
    method: 'PUT',
    body: body ? JSON.stringify(body) : undefined,
  })
}

/**
 * Make an authenticated DELETE request
 */
export async function apiDelete(endpoint: string, options: RequestInit = {}): Promise<Response> {
  return apiRequest(endpoint, { ...options, method: 'DELETE' })
}

/**
 * Make an authenticated PATCH request
 */
export async function apiPatch(
  endpoint: string,
  body?: unknown,
  options: RequestInit = {}
): Promise<Response> {
  return apiRequest(endpoint, {
    ...options,
    method: 'PATCH',
    body: body ? JSON.stringify(body) : undefined,
  })
}

/**
 * Upload a file with automatic token refresh
 */
export async function apiUpload(
  endpoint: string,
  formData: FormData,
  options: RequestInit = {}
): Promise<Response> {
  const url = endpoint.startsWith('/') ? endpoint : `${API_BASE}/${endpoint}`

  // Don't set Content-Type for FormData - browser will set it with boundary
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }
  // Remove Content-Type if it was set, let browser handle it
  delete headers['Content-Type']

  let response = await fetch(url, {
    ...options,
    method: 'POST',
    headers,
    body: formData,
    credentials: 'same-origin',
  })

  // If unauthorized, attempt token refresh and retry
  if (response.status === 401) {
    const refreshed = await refreshAccessToken()

    if (refreshed) {
      response = await fetch(url, {
        ...options,
        method: 'POST',
        headers,
        body: formData,
        credentials: 'same-origin',
      })
    } else {
      const authStore = useAuthStore()
      // Pass null to stay on current page (no redirect)
      authStore.handleTokenExpired('Your session has expired. Please log in again.', undefined)
    }
  }

  return response
}

/**
 * PUT request with FormData (for multipart updates)
 */
export async function apiPutFormData(
  endpoint: string,
  formData: FormData,
  options: RequestInit = {}
): Promise<Response> {
  const url = endpoint.startsWith('/') ? endpoint : `${API_BASE}/${endpoint}`

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }
  delete headers['Content-Type']

  let response = await fetch(url, {
    ...options,
    method: 'PUT',
    headers,
    body: formData,
    credentials: 'same-origin',
  })

  if (response.status === 401) {
    const refreshed = await refreshAccessToken()

    if (refreshed) {
      response = await fetch(url, {
        ...options,
        method: 'PUT',
        headers,
        body: formData,
        credentials: 'same-origin',
      })
    } else {
      const authStore = useAuthStore()
      authStore.handleTokenExpired('Your session has expired. Please log in again.', undefined)
    }
  }

  return response
}

// =============================================================================
// Library API Methods
// =============================================================================

export interface LibraryDocument {
  use_images?: boolean
  pages_dir_path?: string | null
  total_pages?: number | null
  id: number
  title: string
  description: string | null
  cover_image_path: string | null
  views_count: number
  likes_count: number
  comments_count: number
  created_at: string
  uploader: {
    id: number
    name: string | null
  }
}

export interface LibraryDocumentList {
  documents: LibraryDocument[]
  total: number
  page: number
  page_size: number
}

export interface LibraryDanmaku {
  id: number
  document_id: number
  user_id: number
  page_number: number
  position_x: number | null
  position_y: number | null
  selected_text: string | null
  text_bbox: { x: number; y: number; width: number; height: number } | null
  content: string
  color: string | null
  highlight_color: string | null
  created_at: string
  user: {
    id: number | null
    name: string | null
    avatar: string | null
  }
  likes_count: number
  is_liked: boolean
  replies_count: number
}

export interface LibraryDanmakuReply {
  id: number
  danmaku_id: number
  user_id: number
  parent_reply_id: number | null
  content: string
  created_at: string
  user: {
    id: number | null
    name: string | null
    avatar: string | null
  }
}

export interface CreateDanmakuData {
  content: string
  page_number: number
  position_x?: number | null
  position_y?: number | null
  selected_text?: string | null
  text_bbox?: { x: number; y: number; width: number; height: number } | null
  color?: string | null
  highlight_color?: string | null
}

export interface LibraryBookmark {
  id: number
  uuid: string
  document_id: number
  user_id: number
  page_number: number
  note: string | null
  created_at: string
  updated_at: string
  document?: {
    id: number
    title: string
  } | null
}

export interface CreateBookmarkData {
  page_number: number
  note?: string | null
}

export interface CreateReplyData {
  content: string
  parent_reply_id?: number | null
}

// =============================================================================
// Community API Methods
// =============================================================================

export interface CommunityPostAuthor {
  id: number
  name: string | null
  avatar: string | null
  organization?: string | null
}

export interface CommunityPost {
  id: string
  title: string
  description: string | null
  category: string | null
  diagram_type: string
  thumbnail_url: string | null
  spec_json_url?: string
  author: CommunityPostAuthor
  likes_count: number
  comments_count: number
  created_at: string
  is_liked: boolean
  can_edit?: boolean
}

export interface CommunityPostList {
  posts: CommunityPost[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface CreateCommunityPostParams {
  title: string
  description: string
  category: string | null
  diagram_type: string
  spec: Record<string, unknown>
  thumbnail: Blob
}

export async function getCommunityPosts(
  params: {
    page?: number
    pageSize?: number
    mine?: boolean
    type?: string
    category?: string
    sort?: string
  } = {}
): Promise<CommunityPostList> {
  const searchParams = new URLSearchParams()
  searchParams.set('page', String(params.page ?? 1))
  searchParams.set('page_size', String(params.pageSize ?? 20))
  if (params.mine) searchParams.set('mine', '1')
  if (params.type) searchParams.set('type', params.type)
  if (params.category) searchParams.set('category', params.category)
  if (params.sort) searchParams.set('sort', params.sort)

  const response = await apiGet(`/api/community/posts?${searchParams.toString()}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to fetch posts' }))
    throw new Error(err.detail || 'Failed to fetch community posts')
  }
  return response.json()
}

export async function getCommunityPost(
  postId: string
): Promise<CommunityPost & { spec?: unknown }> {
  const response = await apiGet(`/api/community/posts/${postId}`)
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Post not found')
    }
    const err = await response.json().catch(() => ({ detail: 'Failed to fetch post' }))
    throw new Error(err.detail || 'Failed to fetch post')
  }
  return response.json()
}

export async function createCommunityPost(
  data: CreateCommunityPostParams
): Promise<{ message: string; post: CommunityPost }> {
  const formData = new FormData()
  formData.append('title', data.title)
  formData.append('description', data.description)
  formData.append('category', data.category || '')
  formData.append('diagram_type', data.diagram_type)
  formData.append('spec', JSON.stringify(data.spec))
  formData.append('thumbnail', data.thumbnail, 'thumbnail.png')

  const response = await apiUpload('/api/community/posts', formData)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to create post' }))
    throw new Error(err.detail || 'Failed to create post')
  }
  return response.json()
}

export async function updateCommunityPost(
  postId: string,
  data: {
    title: string
    description: string
    category: string | null
    diagram_type: string
    spec: Record<string, unknown>
    thumbnail?: Blob
  }
): Promise<{ message: string; post: CommunityPost }> {
  const formData = new FormData()
  formData.append('title', data.title)
  formData.append('description', data.description)
  formData.append('category', data.category || '')
  formData.append('diagram_type', data.diagram_type)
  formData.append('spec', JSON.stringify(data.spec))
  if (data.thumbnail) {
    formData.append('thumbnail', data.thumbnail, 'thumbnail.png')
  }

  const response = await apiPutFormData(`/api/community/posts/${postId}`, formData)

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to update post' }))
    throw new Error(err.detail || 'Failed to update post')
  }
  return response.json()
}

export async function deleteCommunityPost(postId: string): Promise<{ message: string }> {
  const response = await apiDelete(`/api/community/posts/${postId}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to delete post' }))
    throw new Error(err.detail || 'Failed to delete post')
  }
  return response.json()
}

export async function toggleCommunityPostLike(
  postId: string
): Promise<{ is_liked: boolean; likes_count: number }> {
  const response = await apiPost(`/api/community/posts/${postId}/like`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to toggle like' }))
    throw new Error(err.detail || 'Failed to toggle like')
  }
  return response.json()
}

export interface CommunityPostComment {
  id: number
  content: string
  author: CommunityPostAuthor
  created_at: string
  can_delete?: boolean
}

export interface CommunityPostCommentsResponse {
  comments: CommunityPostComment[]
  total: number
  page: number
  page_size: number
}

export interface CommunityPostLikesResponse {
  names: string[]
  total: number
}

export async function getCommunityPostLikes(
  postId: string,
  limit = 5
): Promise<CommunityPostLikesResponse> {
  const params = new URLSearchParams({ limit: String(limit) })
  const response = await apiGet(`/api/community/posts/${postId}/likes?${params}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to fetch likes' }))
    throw new Error(err.detail || 'Failed to fetch likes')
  }
  return response.json()
}

export async function getCommunityPostComments(
  postId: string,
  page = 1,
  pageSize = 50
): Promise<CommunityPostCommentsResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  const response = await apiGet(`/api/community/posts/${postId}/comments?${params}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to fetch comments' }))
    throw new Error(err.detail || 'Failed to fetch comments')
  }
  return response.json()
}

export async function createCommunityPostComment(
  postId: string,
  content: string
): Promise<{ message: string; comment: CommunityPostComment }> {
  const formData = new FormData()
  formData.append('content', content)
  const response = await apiUpload(`/api/community/posts/${postId}/comments`, formData)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to add comment' }))
    throw new Error(err.detail || 'Failed to add comment')
  }
  return response.json()
}

export async function deleteCommunityPostComment(
  postId: string,
  commentId: number
): Promise<{ message: string }> {
  const response = await apiDelete(`/api/community/posts/${postId}/comments/${commentId}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to delete comment' }))
    throw new Error(err.detail || 'Failed to delete comment')
  }
  return response.json()
}

// =============================================================================
// Library API Methods
// =============================================================================

/**
 * Get list of library documents
 */
export async function getLibraryDocuments(
  page: number = 1,
  pageSize: number = 20,
  search?: string
): Promise<LibraryDocumentList> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
  })
  if (search) {
    params.append('search', search)
  }
  const response = await apiGet(`/api/library/documents?${params.toString()}`)
  if (!response.ok) {
    throw new Error('Failed to fetch library documents')
  }
  return response.json()
}

/**
 * Get a single library document
 */
export async function getLibraryDocument(documentId: number): Promise<LibraryDocument> {
  const response = await apiGet(`/api/library/documents/${documentId}`)
  if (!response.ok) {
    if (response.status === 404) {
      const error = await response.json().catch(() => ({ detail: 'Document not found' }))
      throw new Error(`404: ${error.detail || 'Document not found'}`)
    }
    const error = await response
      .json()
      .catch(() => ({ detail: 'Failed to fetch library document' }))
    throw new Error(error.detail || 'Failed to fetch library document')
  }
  return response.json()
}

// PDF file URL function removed - PDF viewing no longer supported
// Use getLibraryDocumentPageImageUrl() for image-based documents instead

/**
 * Get cover image URL
 */
export function getLibraryDocumentCoverUrl(documentId: number): string {
  return `/api/library/documents/${documentId}/cover`
}

/**
 * Get URL for a page image (for image-based documents)
 */
export function getLibraryDocumentPageImageUrl(documentId: number, pageNumber: number): string {
  return `/api/library/documents/${documentId}/pages/${pageNumber}`
}

/**
 * Upload PDF document (for future admin panel)
 */
export async function uploadLibraryDocument(
  file: File,
  title: string,
  description?: string
): Promise<LibraryDocument> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('title', title)
  if (description) {
    formData.append('description', description)
  }
  const response = await apiUpload('/api/library/documents', formData)
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(error.detail || 'Failed to upload document')
  }
  return response.json()
}

/**
 * Update document metadata (for future admin panel)
 */
export async function updateLibraryDocument(
  documentId: number,
  data: { title?: string; description?: string }
): Promise<LibraryDocument> {
  const response = await apiPut(`/api/library/documents/${documentId}`, data)
  if (!response.ok) {
    throw new Error('Failed to update document')
  }
  return response.json()
}

/**
 * Upload cover image (for future admin panel)
 */
export async function uploadLibraryDocumentCover(
  documentId: number,
  file: File
): Promise<{ cover_image_path: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiUpload(`/api/library/documents/${documentId}/cover`, formData)
  if (!response.ok) {
    throw new Error('Failed to upload cover image')
  }
  return response.json()
}

/**
 * Delete document (for future admin panel)
 */
export async function deleteLibraryDocument(documentId: number): Promise<void> {
  const response = await apiDelete(`/api/library/documents/${documentId}`)
  if (!response.ok) {
    throw new Error('Failed to delete document')
  }
}

/**
 * Get danmaku for a document
 */
export async function getDanmaku(
  documentId: number,
  pageNumber?: number,
  selectedText?: string
): Promise<{ danmaku: LibraryDanmaku[] }> {
  const params = new URLSearchParams()
  if (pageNumber !== undefined) {
    params.append('page_number', pageNumber.toString())
  }
  if (selectedText) {
    params.append('selected_text', selectedText)
  }
  const queryString = params.toString()
  const endpoint = `/api/library/documents/${documentId}/danmaku${queryString ? `?${queryString}` : ''}`
  const response = await apiGet(endpoint)
  if (!response.ok) {
    throw new Error('Failed to fetch danmaku')
  }
  return response.json()
}

/**
 * Get recent danmaku across all documents
 */
export async function getRecentDanmaku(limit: number = 50): Promise<{ danmaku: LibraryDanmaku[] }> {
  const response = await apiGet(`/api/library/danmaku/recent?limit=${limit}`)
  if (!response.ok) {
    throw new Error('Failed to fetch recent danmaku')
  }
  return response.json()
}

/**
 * Create danmaku comment
 */
export async function createDanmaku(
  documentId: number,
  data: CreateDanmakuData
): Promise<{ id: number; message: string; danmaku: LibraryDanmaku }> {
  const response = await apiPost(`/api/library/documents/${documentId}/danmaku`, data)
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create danmaku' }))
    throw new Error(error.detail || 'Failed to create danmaku')
  }
  return response.json()
}

/**
 * Toggle like on danmaku
 */
export async function likeDanmaku(
  danmakuId: number
): Promise<{ is_liked: boolean; likes_count: number }> {
  const response = await apiPost(`/api/library/danmaku/${danmakuId}/like`)
  if (!response.ok) {
    throw new Error('Failed to toggle like')
  }
  return response.json()
}

/**
 * Get replies to a danmaku
 */
export async function getDanmakuReplies(
  danmakuId: number
): Promise<{ replies: LibraryDanmakuReply[] }> {
  const response = await apiGet(`/api/library/danmaku/${danmakuId}/replies`)
  if (!response.ok) {
    throw new Error('Failed to fetch replies')
  }
  return response.json()
}

/**
 * Reply to a danmaku
 */
export async function replyToDanmaku(
  danmakuId: number,
  data: CreateReplyData
): Promise<{ id: number; message: string; reply: LibraryDanmakuReply }> {
  const response = await apiPost(`/api/library/danmaku/${danmakuId}/replies`, data)
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create reply' }))
    throw new Error(error.detail || 'Failed to create reply')
  }
  return response.json()
}

/**
 * Update danmaku position
 * Only the creator or admin can update position.
 */
export interface UpdateDanmakuPositionData {
  position_x?: number | null
  position_y?: number | null
}

export async function updateDanmakuPosition(
  danmakuId: number,
  data: UpdateDanmakuPositionData
): Promise<void> {
  const response = await apiPatch(`/api/library/danmaku/${danmakuId}`, data)
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: 'Failed to update danmaku position' }))
    throw new Error(error.detail || '只能移动自己的评论')
  }
}

/**
 * Delete own danmaku
 * Only the creator can delete their own danmaku.
 */
export async function deleteDanmaku(danmakuId: number): Promise<void> {
  const response = await apiDelete(`/api/library/danmaku/${danmakuId}`)
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete danmaku' }))
    throw new Error(error.detail || '只能删除自己的评论')
  }
}

/**
 * Delete own reply
 */
export async function deleteDanmakuReply(replyId: number): Promise<void> {
  const response = await apiDelete(`/api/library/danmaku/replies/${replyId}`)
  if (!response.ok) {
    throw new Error('Failed to delete reply')
  }
}

/**
 * Create or update a bookmark
 */
export async function createBookmark(
  documentId: number,
  data: CreateBookmarkData
): Promise<{ id: number; message: string; bookmark: LibraryBookmark }> {
  const url = `/api/library/documents/${documentId}/bookmarks`
  const response = await apiPost(url, data)
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create bookmark' }))
    if (import.meta.env.DEV) {
      console.error('[apiClient] createBookmark error:', error)
    }
    throw new Error(error.detail || 'Failed to create bookmark')
  }
  const result = await response.json()
  return result
}

/**
 * Get recent bookmarks
 */
export async function getRecentBookmarks(
  limit: number = 50
): Promise<{ bookmarks: LibraryBookmark[] }> {
  const response = await apiGet(`/api/library/bookmarks/recent?limit=${limit}`)
  if (!response.ok) {
    throw new Error('Failed to fetch recent bookmarks')
  }
  return response.json()
}

/**
 * Get bookmark for a specific document page
 * Returns null if bookmark doesn't exist (404)
 * Throws error for other failures
 */
export async function getBookmark(
  documentId: number,
  pageNumber: number
): Promise<LibraryBookmark | null> {
  try {
    const response = await apiGet(`/api/library/documents/${documentId}/bookmarks/${pageNumber}`)
    if (!response.ok) {
      // 404 means bookmark doesn't exist or doesn't belong to user - this is expected
      if (response.status === 404) {
        return null
      }
      const error = await response.json().catch(() => ({ detail: 'Failed to fetch bookmark' }))
      throw new Error(error.detail || 'Failed to fetch bookmark')
    }
    const data = await response.json()
    return data || null
  } catch (error) {
    // If it's a network error that might be a 404, return null instead of throwing
    // This prevents console errors for expected missing bookmarks
    if (error instanceof TypeError && error.message.includes('fetch')) {
      // Network error - might be 404, return null to indicate no bookmark
      return null
    }
    throw error
  }
}

/**
 * Get bookmark by UUID
 * Throws error with 404 message if bookmark doesn't exist or doesn't belong to user
 */
export async function getBookmarkByUuid(bookmarkUuid: string): Promise<LibraryBookmark> {
  const response = await apiGet(`/api/library/bookmarks/${bookmarkUuid}`)
  if (!response.ok) {
    if (response.status === 404) {
      const error = await response.json().catch(() => ({ detail: 'Bookmark not found' }))
      throw new Error(`404: ${error.detail || 'Bookmark not found'}`)
    }
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch bookmark' }))
    throw new Error(error.detail || 'Failed to fetch bookmark')
  }
  return response.json()
}

/**
 * Delete a bookmark
 */
export async function deleteBookmark(bookmarkId: number): Promise<void> {
  const response = await apiDelete(`/api/library/bookmarks/${bookmarkId}`)
  if (!response.ok) {
    throw new Error('Failed to delete bookmark')
  }
}

// Export default object for convenience
export default {
  request: apiRequest,
  get: apiGet,
  post: apiPost,
  put: apiPut,
  delete: apiDelete,
  patch: apiPatch,
  upload: apiUpload,
}
