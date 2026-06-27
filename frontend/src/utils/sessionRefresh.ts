/**
 * Shared mutex for POST /api/auth/refresh (httpOnly cookie rotation).
 *
 * Both the Pinia auth store and apiClient must use this helper so idle-tab
 * recovery and API 401 retries do not race duplicate refresh requests.
 */
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'

const API_BASE = '/api'

let isRefreshing = false
let refreshPromise: Promise<boolean> | null = null

export async function refreshSessionAccessToken(): Promise<boolean> {
  if (isMindgraphHeadlessExportSession()) {
    return false
  }
  if (isRefreshing && refreshPromise) {
    return refreshPromise
  }

  isRefreshing = true
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'same-origin',
      })
      return response.ok
    } catch {
      return false
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()

  return refreshPromise
}
