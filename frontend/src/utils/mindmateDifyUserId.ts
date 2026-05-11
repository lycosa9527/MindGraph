/**
 * Dify `user` for MindMate — mirrors `utils.dify_mindmate_user_id` (Bayi SSO UUID in `phone`).
 */
import type { AuthMode } from '@/types'

function stripUuidWrappers(raw: string): string {
  let s = raw.trim()
  const lower = s.toLowerCase()
  if (lower.startsWith('urn:uuid:')) {
    s = s.slice(9)
  } else if (s.startsWith('{') && s.endsWith('}')) {
    s = s.slice(1, -1)
  }
  return s.trim()
}

function normalizeUuidLike(raw: string): string | null {
  const s = stripUuidWrappers(raw)
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s)) {
    return s.toLowerCase()
  }
  const compact = s.replace(/-/g, '')
  if (!/^[0-9a-f]{32}$/i.test(compact)) {
    return null
  }
  const h = compact.toLowerCase()
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
}

export function mindmateDifyUserIdFromSession(
  authMode: AuthMode,
  mindgraphUserId: string,
  phone?: string | null
): string {
  if (authMode === 'bayi' && phone) {
    const canonical = normalizeUuidLike(phone)
    if (canonical) {
      return canonical
    }
  }
  return `mg_user_${mindgraphUserId}`
}
