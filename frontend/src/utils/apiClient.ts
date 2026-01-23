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
        // Token refreshed successfully - cookies are automatically updated
        console.debug('[ApiClient] Token refreshed successfully')
        return true
      }

      // Refresh failed - token expired or invalid
      console.debug('[ApiClient] Token refresh failed:', response.status)
      return false
    } catch (error) {
      console.error('[ApiClient] Token refresh error:', error)
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

    console.debug('[ApiClient] Got 401, attempting token refresh')
    const refreshed = await refreshAccessToken()

    if (refreshed) {
      // Retry the original request with the new token
      console.debug('[ApiClient] Retrying request after token refresh')
      response = await fetch(url, {
        ...options,
        headers,
        credentials: 'same-origin',
      })
    } else {
      // Refresh failed - trigger session expired modal
      console.debug('[ApiClient] Refresh failed, showing login modal')
      const authStore = useAuthStore()
      // Pass null to stay on current page (no redirect)
      authStore.handleTokenExpired('Your session has expired. Please log in again.', null)
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
    console.debug('[ApiClient] Got 401 on upload, attempting token refresh')
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
      authStore.handleTokenExpired('Your session has expired. Please log in again.', null)
    }
  }

  return response
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
