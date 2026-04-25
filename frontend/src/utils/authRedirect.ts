import type { LocationQueryValue } from 'vue-router'

/**
 * Post-login redirect from `/auth?redirect=…` (and quick-reg success).
 * Only same-origin path-style targets are allowed to avoid open redirects.
 */
export function getSafePostAuthPath(
  queryRedirect: LocationQueryValue | LocationQueryValue[] | undefined,
  fallback = '/mindmate'
): string {
  if (queryRedirect == null) {
    return fallback
  }
  const raw = Array.isArray(queryRedirect) ? queryRedirect[0] : queryRedirect
  if (raw == null || typeof raw !== 'string') {
    return fallback
  }
  const t = raw.trim()
  if (!t) {
    return fallback
  }
  if (t.length > 2048) {
    return fallback
  }
  if (!t.startsWith('/')) {
    return fallback
  }
  if (t.startsWith('//') || t.includes('://')) {
    return fallback
  }
  if (/[\0\r\n]/.test(t)) {
    return fallback
  }
  return t
}
