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
import type { LocaleCode } from '@/i18n/locales'
import { useAuthStore } from '@/stores/auth'
import { useUIStore } from '@/stores/ui'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'
import { refreshSessionAccessToken } from '@/utils/sessionRefresh'

const API_BASE = '/api'

/** Dev: bypass Vite proxy for multipart uploads (large showcase publishes). */
function resolveUploadFetchTarget(endpoint: string): { url: string; credentials: RequestCredentials } {
  const path = endpoint.startsWith('/') ? endpoint : `${API_BASE}/${endpoint}`
  const devOrigin = typeof __DEV_API_ORIGIN__ === 'string' ? __DEV_API_ORIGIN__.trim() : ''
  if (import.meta.env.PROD || !devOrigin) {
    return { url: path, credentials: 'same-origin' }
  }
  return { url: `${devOrigin}${path}`, credentials: 'include' }
}

/** True only for the session token refresh route (not e.g. refresh-invitation-code). */
function isSessionTokenRefreshEndpoint(endpointOrUrl: string): boolean {
  const path = endpointOrUrl.split('?')[0] ?? endpointOrUrl
  return path === '/api/auth/refresh' || path.endsWith('/api/auth/refresh')
}

/** Current UI language for API `X-Language` (backend maps to zh / en / az for Messages). */
function currentUiLocaleCodeForHeaders(): string {
  return useUIStore().language as LocaleCode
}

/** Read double-submit CSRF token from cookie (set by backend on authenticated responses). */
function readCsrfTokenFromCookie(): string | null {
  if (typeof document === 'undefined') {
    return null
  }
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

function mergeApiHeaders(
  base: Record<string, string>,
  options?: RequestInit
): Record<string, string> {
  const fromCaller = (options?.headers as Record<string, string>) ?? {}
  const csrfToken = readCsrfTokenFromCookie()
  const merged: Record<string, string> = {
    'X-Language': currentUiLocaleCodeForHeaders(),
    ...base,
    ...fromCaller,
  }
  if (csrfToken && !merged['X-CSRF-Token']) {
    merged['X-CSRF-Token'] = csrfToken
  }
  return merged
}

// Refresh mutex lives in sessionRefresh.ts (shared with auth store).

/**
 * Attempt to refresh the access token using the refresh token cookie
 * Returns true if refresh successful, false otherwise
 */
async function refreshAccessToken(): Promise<boolean> {
  return refreshSessionAccessToken()
}

function handleUploadUnauthorizedAfterRetry(): void {
  const authStore = useAuthStore()
  authStore.handleTokenExpired('Your session has expired. Please log in again.', undefined)
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

  const headers = mergeApiHeaders(
    {
      'Content-Type': 'application/json',
    },
    options
  )

  // Make the initial request
  let response = await fetch(url, {
    ...options,
    headers,
    credentials: 'same-origin', // Include cookies
  })

  // If unauthorized, attempt token refresh and retry
  if (response.status === 401) {
    if (isMindgraphHeadlessExportSession()) {
      return response
    }
    // Don't retry refresh endpoint to avoid infinite loop
    if (isSessionTokenRefreshEndpoint(endpoint) || isSessionTokenRefreshEndpoint(url)) {
      return response
    }

    const authStore = useAuthStore()
    // Check if user was previously authenticated (before refresh attempt)
    const hadUserBeforeRefresh = !!authStore.user || !!sessionStorage.getItem('auth_user')

    const refreshed = await refreshAccessToken()

    if (refreshed) {
      const retryHeaders = mergeApiHeaders(
        {
          'Content-Type': 'application/json',
        },
        options
      )
      response = await fetch(url, {
        ...options,
        headers: retryHeaders,
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

function parseApiErrorDetail(payload: unknown, fallback: string): string {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const lines = detail
        .map((item) => {
          if (!item || typeof item !== 'object') return null
          const loc = Array.isArray((item as { loc?: unknown }).loc)
            ? (item as { loc: unknown[] }).loc
                .filter((part) => part !== 'body')
                .join('.')
            : ''
          const msg = (item as { msg?: unknown }).msg
          if (typeof msg !== 'string' || !msg.trim()) return null
          return loc ? `${loc}: ${msg}` : msg
        })
        .filter((line): line is string => Boolean(line))
      if (lines.length > 0) return lines.join('\n')
    }
  }
  return fallback
}

/**
 * JSON API request — parses the body and throws on non-OK responses.
 */
export async function apiRequestJson<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await apiRequest(endpoint, options)
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(parseApiErrorDetail(payload, response.statusText || 'Request failed'))
  }
  return response.json() as Promise<T>
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
 * Clone FormData so uploads can be retried (browser streams are single-use).
 */
function cloneFormData(formData: FormData): FormData {
  const copy = new FormData()
  for (const [key, value] of formData.entries()) {
    if (value instanceof File) {
      copy.append(key, value, value.name)
    } else {
      copy.append(key, value)
    }
  }
  return copy
}

/**
 * Upload a file with automatic token refresh
 */
export async function apiUpload(
  endpoint: string,
  formData: FormData,
  options: RequestInit = {}
): Promise<Response> {
  const { url, credentials } = resolveUploadFetchTarget(endpoint)

  const merged = mergeApiHeaders({}, options)
  // Remove Content-Type if it was set, let browser handle it
  delete merged['Content-Type']

  const uploadOnce = () =>
    fetch(url, {
      ...options,
      method: 'POST',
      headers: merged,
      body: cloneFormData(formData),
      credentials,
    })

  let response: Response
  try {
    response = await uploadOnce()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to fetch'
    throw new Error(message === 'Failed to fetch' ? 'NETWORK_ERROR' : message)
  }

  // If unauthorized, attempt token refresh and retry
  if (response.status === 401) {
    if (isMindgraphHeadlessExportSession()) {
      return response
    }
    const refreshed = await refreshAccessToken()

    if (refreshed) {
      try {
        response = await uploadOnce()
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch'
        throw new Error(message === 'Failed to fetch' ? 'NETWORK_ERROR' : message)
      }
      if (response.status === 401) {
        handleUploadUnauthorizedAfterRetry()
        throw new Error('SESSION_EXPIRED')
      }
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
  const { url, credentials } = resolveUploadFetchTarget(endpoint)

  const merged = mergeApiHeaders({}, options)
  delete merged['Content-Type']

  const uploadOnce = () =>
    fetch(url, {
      ...options,
      method: 'PUT',
      headers: merged,
      body: cloneFormData(formData),
      credentials,
    })

  let response: Response
  try {
    response = await uploadOnce()
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to fetch'
    throw new Error(message === 'Failed to fetch' ? 'NETWORK_ERROR' : message)
  }

  if (response.status === 401) {
    if (isMindgraphHeadlessExportSession()) {
      return response
    }
    const refreshed = await refreshAccessToken()

    if (refreshed) {
      try {
        response = await uploadOnce()
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch'
        throw new Error(message === 'Failed to fetch' ? 'NETWORK_ERROR' : message)
      }
      if (response.status === 401) {
        handleUploadUnauthorizedAfterRetry()
        throw new Error('SESSION_EXPIRED')
      }
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
// Showcase API Methods
// =============================================================================

export interface ShowcasePost {
  id: string
  title: string
  description: string | null
  tags: string[]
  case_type: 'teaching_design' | 'diagram_case' | 'diagram_template'
  subject: string | null
  grade: string | null
  diagram_type: string | null
  thumbnail_url: string | null
  spec_json_url?: string | null
  attachment_url?: string | null
  classroom_video_url?: string | null
  reflection_video_url?: string | null
  source_file_url?: string | null
  gallery_items?: Array<{
    kind: 'image' | 'diagram'
    url?: string | null
    missing?: boolean
    filename?: string | null
    diagram_id?: string | null
    title?: string | null
    diagram_type?: string | null
    spec?: Record<string, unknown>
  }>
  status: 'pending' | 'approved' | 'rejected' | 'withdrawn'
  is_expert_recommended: boolean
  publish_source?: 'self' | 'proxy'
  attribution?: { display_name?: string; organization?: string | null; is_external?: boolean } | null
  rejection_reason?: string | null
  author: CommunityPostAuthor & { is_proxy?: boolean }
  likes_count: number
  views_count: number
  created_at: string
  reviewed_at?: string | null
  reviewer?: { id: number; name: string } | null
  expert_recommender?: { id: number; name: string } | null
  expert_recommended_at?: string | null
  is_liked: boolean
  is_favorited: boolean
  can_edit?: boolean
  can_delete?: boolean
  can_withdraw?: boolean
  can_delist?: boolean
  can_resubmit?: boolean
  can_review?: boolean
  can_expert_recommend?: boolean
}

export interface ShowcaseMeta {
  subjects: string[]
  grades: string[]
  recommended_tags: string[]
  diagram_types: string[]
  case_types: string[]
}

export interface ShowcasePostList {
  posts: ShowcasePost[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

function normalizeShowcasePost(post: ShowcasePost): ShowcasePost {
  return {
    ...post,
    is_favorited: Boolean(post.is_favorited),
    is_liked: Boolean(post.is_liked),
  }
}

export async function getShowcasePosts(
  params: {
    page?: number
    pageSize?: number
    caseType?: string
    expertRecommended?: boolean
    subject?: string
    grade?: string
    diagramType?: string
    publishSource?: string
    sort?: string
    search?: string
    mine?: boolean
    favorited?: boolean
    status?: string
  } = {}
): Promise<ShowcasePostList> {
  const searchParams = new URLSearchParams()
  searchParams.set('page', String(params.page ?? 1))
  searchParams.set('page_size', String(params.pageSize ?? 20))
  if (params.caseType) searchParams.set('case_type', params.caseType)
  if (params.expertRecommended) searchParams.set('expert_recommended', 'true')
  if (params.subject) searchParams.set('subject', params.subject)
  if (params.grade) searchParams.set('grade', params.grade)
  if (params.diagramType) searchParams.set('diagram_type', params.diagramType)
  if (params.publishSource) searchParams.set('publish_source', params.publishSource)
  if (params.sort) searchParams.set('sort', params.sort)
  if (params.search) searchParams.set('search', params.search)
  if (params.mine) searchParams.set('mine', '1')
  if (params.favorited) searchParams.set('favorited', '1')
  if (params.status) searchParams.set('status', params.status)

  const response = await apiGet(`/api/showcase/posts?${searchParams.toString()}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to fetch cases' }))
    throw new Error(err.detail || 'Failed to fetch cases')
  }
  const data = (await response.json()) as ShowcasePostList
  return {
    ...data,
    posts: data.posts.map(normalizeShowcasePost),
  }
}

export async function getShowcasePost(
  postId: string
): Promise<ShowcasePost & { spec?: unknown }> {
  const response = await apiGet(`/api/showcase/posts/${postId}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to fetch case' }))
    throw new Error(parseApiErrorDetail(err, 'Failed to fetch case'))
  }
  const data = (await response.json()) as ShowcasePost & { spec?: unknown }
  return normalizeShowcasePost(data)
}

export async function createShowcasePost(formData: FormData): Promise<{ message: string; post: ShowcasePost }> {
  let response: Response
  try {
    response = await apiUpload('/api/showcase/posts', formData)
  } catch (e) {
    if (e instanceof Error && e.message === 'NETWORK_ERROR') {
      throw new Error('NETWORK_ERROR')
    }
    throw e
  }
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('SESSION_EXPIRED')
    }
    const err = await response.json().catch(() => ({ detail: 'Failed to publish case' }))
    const detail = err.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail) && detail[0]?.msg
          ? String(detail[0].msg)
          : 'Failed to publish case'
    throw new Error(message)
  }
  return response.json()
}

async function parseShowcaseFormError(response: Response, fallback: string): Promise<never> {
  const err = await response.json().catch(() => ({ detail: fallback }))
  const detail = err.detail
  const message =
    typeof detail === 'string'
      ? detail
      : Array.isArray(detail) && detail[0]?.msg
        ? String(detail[0].msg)
        : fallback
  throw new Error(message)
}

export async function updateShowcasePost(
  postId: string,
  formData: FormData
): Promise<{ message: string; post: ShowcasePost }> {
  const id = postId.trim()
  if (!id) {
    throw new Error('Missing case id')
  }
  let response: Response
  try {
    response = await apiPutFormData(`/api/showcase/posts/${id}`, formData)
  } catch (e) {
    if (e instanceof Error && e.message === 'NETWORK_ERROR') {
      throw new Error('NETWORK_ERROR')
    }
    throw e
  }
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('SESSION_EXPIRED')
    }
    await parseShowcaseFormError(response, 'Failed to update case')
  }
  return response.json()
}

export async function uploadShowcaseGalleryImages(
  postId: string,
  formData: FormData
): Promise<{ message: string; post: ShowcasePost }> {
  const id = postId.trim()
  if (!id) {
    throw new Error('Missing case id')
  }
  let response: Response
  try {
    response = await apiUpload(`/api/showcase/posts/${id}/gallery-images`, formData)
  } catch (e) {
    if (e instanceof Error && e.message === 'NETWORK_ERROR') {
      throw new Error('NETWORK_ERROR')
    }
    throw e
  }
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('SESSION_EXPIRED')
    }
    const err = await response.json().catch(() => ({ detail: 'Failed to upload gallery images' }))
    const detail = err.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail) && detail[0]?.msg
          ? String(detail[0].msg)
          : 'Failed to upload gallery images'
    throw new Error(`${response.status}: ${message}`)
  }
  const data = await response.json()
  return {
    message: data.message,
    post: normalizeShowcasePost(data.post),
  }
}

export async function withdrawShowcasePost(postId: string): Promise<{ message: string }> {
  const id = postId.trim()
  if (!id) {
    throw new Error('Missing case id')
  }
  const response = await apiPost(`/api/showcase/posts/${id}/withdraw`, {})
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to withdraw case' }))
    throw new Error(err.detail || 'Failed to withdraw case')
  }
  return response.json()
}

export async function delistShowcasePost(
  postId: string
): Promise<{ message: string; post: ShowcasePost }> {
  const id = postId.trim()
  if (!id) {
    throw new Error('Missing case id')
  }
  const response = await apiPost(`/api/showcase/posts/${id}/delist`, {})
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to delist case' }))
    throw new Error(err.detail || 'Failed to delist case')
  }
  const data = (await response.json()) as { message: string; post: ShowcasePost }
  return { ...data, post: normalizeShowcasePost(data.post) }
}

export async function deleteShowcasePost(postId: string): Promise<{ message: string }> {
  const id = postId.trim()
  if (!id) {
    throw new Error('Missing case id')
  }
  const response = await apiPost(`/api/showcase/posts/${id}/delete`, {})
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to delete case' }))
    throw new Error(err.detail || 'Failed to delete case')
  }
  return response.json()
}

export async function deleteAdminShowcasePost(postId: string): Promise<{ message: string }> {
  const id = postId.trim()
  if (!id) {
    throw new Error('Missing case id')
  }
  const response = await apiPost(`/api/auth/admin/showcase/posts/${id}/delete`, {})
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to delete case' }))
    throw new Error(err.detail || 'Failed to delete case')
  }
  return response.json()
}

export async function toggleShowcasePostLike(
  postId: string
): Promise<{ liked: boolean; likes_count: number }> {
  const response = await apiPost(`/api/showcase/posts/${postId}/like`, {})
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to toggle like' }))
    throw new Error(err.detail || 'Failed to toggle like')
  }
  return response.json()
}

export async function getShowcaseFavoritePosts(
  params: { page?: number; pageSize?: number } = {}
): Promise<ShowcasePostList> {
  const searchParams = new URLSearchParams()
  searchParams.set('page', String(params.page ?? 1))
  searchParams.set('page_size', String(params.pageSize ?? 100))
  const response = await apiGet(`/api/showcase/favorites?${searchParams.toString()}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to fetch favorite cases' }))
    throw new Error(parseApiErrorDetail(err, 'Failed to fetch favorite cases'))
  }
  const data = (await response.json()) as ShowcasePostList
  return {
    ...data,
    posts: data.posts.map((post) => ({ ...post, is_favorited: true })),
  }
}

export async function toggleShowcasePostFavorite(
  postId: string
): Promise<{ favorited: boolean }> {
  const response = await apiPost(`/api/showcase/posts/${postId}/favorite`, {})
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to toggle favorite' }))
    throw new Error(parseApiErrorDetail(err, 'Failed to toggle favorite'))
  }
  return response.json()
}

export async function toggleShowcaseExpertRecommend(
  postId: string
): Promise<{ is_expert_recommended: boolean; post: ShowcasePost }> {
  const response = await apiPost(`/api/showcase/posts/${postId}/recommend`, {})
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to update recommendation' }))
    throw new Error(parseApiErrorDetail(err, 'Failed to update recommendation'))
  }
  return response.json()
}

export async function reviewShowcasePost(
  postId: string,
  action: 'approve' | 'reject',
  rejectionReason?: string
): Promise<{ message: string; credited_coins: number; post: ShowcasePost }> {
  const id = postId.trim()
  if (!id) {
    throw new Error('Missing case id')
  }
  const response = await apiPost(`/api/showcase/posts/${id}/review`, {
    action,
    rejection_reason: rejectionReason ?? null,
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to review case' }))
    throw new Error(err.detail || 'Failed to review case')
  }
  return response.json()
}

export async function reviewAdminShowcasePost(
  postId: string,
  action: 'approve' | 'reject',
  rejectionReason?: string
): Promise<{ message: string; credited_coins: number; post: ShowcasePost }> {
  const id = postId.trim()
  if (!id) {
    throw new Error('Missing case id')
  }
  const response = await apiPost(`/api/auth/admin/showcase/posts/${id}/review`, {
    action,
    rejection_reason: rejectionReason ?? null,
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to review case' }))
    throw new Error(err.detail || 'Failed to review case')
  }
  return response.json()
}

export async function getShowcasePendingCount(): Promise<{
  count: number
  pending: number
  rejected: number
}> {
  const response = await apiGet('/api/showcase/pending/count')
  if (!response.ok) {
    return { count: 0, pending: 0, rejected: 0 }
  }
  const data = (await response.json()) as { count?: number; pending?: number; rejected?: number }
  const pending = data.pending ?? data.count ?? 0
  const rejected = data.rejected ?? 0
  return { count: pending, pending, rejected }
}

export async function getShowcaseMeta(): Promise<ShowcaseMeta> {
  const response = await apiGet('/api/showcase/meta')
  if (!response.ok) {
    throw new Error('Failed to load showcase meta')
  }
  return response.json()
}

export interface ShowcaseStatsOverview {
  pending: number
  approved_total: number
  rejected_total: number
  total_posts?: number
  created_recent: number
  approved_recent: number
  rejected_recent?: number
  proxy_total: number
  self_total?: number
  expert_recommended_total: number
  rejection_rate_recent: number
  by_case_type?: Record<string, number>
  total_views?: number
  total_likes?: number
  period_days: number
}

export async function getAdminShowcaseStats(): Promise<ShowcaseStatsOverview> {
  const response = await apiGet('/api/auth/admin/showcase/stats/overview')
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to load showcase stats' }))
    const detail = err.detail
    throw new Error(typeof detail === 'string' ? detail : 'Failed to load showcase stats')
  }
  return response.json()
}

export interface ShowcaseStaffGrantRow {
  id: number | null
  user_id: number
  user_name: string | null
  user_phone: string | null
  organization: string | null
  permissions: string[]
  note: string | null
  expires_at: string | null
  granted_by_name?: string | null
  source?: 'grant' | 'builtin'
  builtin_role?: string | null
  editable?: boolean
}

export async function getAdminShowcaseStaffGrants(): Promise<{
  grants: ShowcaseStaffGrantRow[]
  builtin: ShowcaseStaffGrantRow[]
}> {
  const response = await apiGet('/api/auth/admin/showcase/staff-grants')
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to load staff grants' }))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Failed to load staff grants')
  }
  return response.json()
}

export async function saveAdminShowcaseStaffGrant(body: {
  user_id: number
  permissions: string[]
  note?: string
}): Promise<void> {
  const response = await apiPost('/api/auth/admin/showcase/staff-grants', body)
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to save grant' }))
    const detail = err.detail
    throw new Error(typeof detail === 'string' ? detail : 'Failed to save grant')
  }
}

export async function deleteAdminShowcaseStaffGrant(userId: number): Promise<void> {
  const response = await apiDelete(`/api/auth/admin/showcase/staff-grants/${userId}`)
  if (!response.ok) {
    throw new Error('Failed to delete grant')
  }
}

export interface ShowcaseFieldOptionRow {
  id: number
  category: string
  value: string
  label_zh: string
  label_en: string | null
  sort_order: number
  is_active: boolean
}

export async function getAdminShowcaseFieldOptions(includeInactive = true): Promise<{
  options: ShowcaseFieldOptionRow[]
}> {
  const params = includeInactive ? '?include_inactive=true' : ''
  const response = await apiGet(`/api/auth/admin/showcase/field-options${params}`)
  if (!response.ok) {
    throw new Error('Failed to load field options')
  }
  return response.json()
}

export async function createAdminShowcaseFieldOption(body: {
  category: string
  value: string
  label_zh?: string
  sort_order?: number
  is_active?: boolean
}): Promise<void> {
  const response = await apiPost('/api/auth/admin/showcase/field-options', body)
  if (!response.ok) {
    throw new Error('Failed to create field option')
  }
}

export async function patchAdminShowcaseFieldOption(
  id: number,
  body: Partial<{ label_zh: string; sort_order: number; is_active: boolean }>
): Promise<void> {
  const response = await apiRequest(`/api/auth/admin/showcase/field-options/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error('Failed to update field option')
  }
}

export async function deleteAdminShowcaseFieldOption(id: number): Promise<void> {
  const response = await apiDelete(`/api/auth/admin/showcase/field-options/${id}`)
  if (!response.ok) {
    throw new Error('Failed to delete field option')
  }
}

export async function proxyCreateShowcasePost(formData: FormData): Promise<{ post: ShowcasePost }> {
  let response: Response
  try {
    response = await apiUpload('/api/auth/admin/showcase/posts/proxy', formData)
  } catch (e) {
    if (e instanceof Error && e.message === 'NETWORK_ERROR') {
      throw new Error('NETWORK_ERROR')
    }
    throw e
  }
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to create proxy case' }))
    throw new Error(parseApiErrorDetail(err, 'Failed to create proxy case'))
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
