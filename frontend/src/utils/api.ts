/**
 * API Utilities
 * Centralized API calls with authentication support
 *
 * Note: Authentication is now handled via httpOnly cookies (set by backend).
 * The Authorization header is no longer needed - cookies are sent automatically.
 */
import { apiRequest } from './apiClient'

const API_BASE = '/api'

/**
 * Make an authenticated fetch request
 * Uses the new apiClient with automatic token refresh
 */
export async function authFetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const url = endpoint.startsWith('/') ? endpoint : `${API_BASE}/${endpoint}`
  return apiRequest(url, options)
}

