/**
 * Playwright `vueflow_screenshot` init script sets this before the SPA runs so auth
 * and apiClient skip JWT verification and token refresh (no httpOnly cookies in
 * headless). Must match `HEADLESS_EXPORT_SESSION_KEY` in `vueflow_screenshot.py`.
 */
export const MINDGRAPH_HEADLESS_EXPORT_KEY = 'mindgraph_headless_export'

export function isMindgraphHeadlessExportSession(): boolean {
  if (typeof sessionStorage === 'undefined') {
    return false
  }
  try {
    return sessionStorage.getItem(MINDGRAPH_HEADLESS_EXPORT_KEY) === '1'
  } catch {
    return false
  }
}
