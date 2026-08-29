/**
 * Local MindMate collab session tracking (sidebar rejoin list).
 *
 * Persisted in localStorage so public (network) rooms survive tab refresh.
 */

export const LOCAL_MINDMATE_COLLAB_SESSIONS_KEY = 'mindmate_collab_recent_sessions'
export const MINDMATE_COLLAB_ENDED_CODES_KEY = 'mindmate_collab_recently_ended'
export const MINDMATE_COLLAB_SESSIONS_CHANGED_EVENT = 'mindmate-collab-sessions-changed'
export const MINDMATE_COLLAB_SESSION_REMOVED_EVENT = 'mindmate-collab-session-removed'

const ENDED_CODE_TTL_MS = 15_000
const recentlyEndedCodes = new Map<string, number>()

function persistEndedCodes(): void {
  if (typeof localStorage === 'undefined') {
    return
  }
  const now = Date.now()
  const payload: Record<string, number> = {}
  for (const [key, markedAt] of recentlyEndedCodes) {
    if (now - markedAt <= ENDED_CODE_TTL_MS) {
      payload[key] = markedAt
    } else {
      recentlyEndedCodes.delete(key)
    }
  }
  try {
    localStorage.setItem(MINDMATE_COLLAB_ENDED_CODES_KEY, JSON.stringify(payload))
  } catch {
    // quota / privacy mode
  }
}

function hydrateEndedCodesFromStorage(): void {
  if (typeof localStorage === 'undefined') {
    return
  }
  try {
    const raw = localStorage.getItem(MINDMATE_COLLAB_ENDED_CODES_KEY)
    if (!raw) {
      return
    }
    const parsed = JSON.parse(raw) as Record<string, number>
    const now = Date.now()
    for (const [key, markedAt] of Object.entries(parsed)) {
      if (typeof markedAt !== 'number' || now - markedAt > ENDED_CODE_TTL_MS) {
        continue
      }
      const existing = recentlyEndedCodes.get(key)
      if (existing == null || markedAt > existing) {
        recentlyEndedCodes.set(key, markedAt)
      }
    }
  } catch {
    // ignore corrupt storage
  }
}

/** Remember a room code so stop/teardown does not immediately rejoin it. */
export function markMindmateCollabCodeEnded(code: string): void {
  recentlyEndedCodes.set(normalizeMindmateCollabCode(code), Date.now())
  persistEndedCodes()
}

/** True when this invite code was just ended (this tab or another tab on the same origin). */
export function wasMindmateCollabCodeRecentlyEnded(code: string): boolean {
  hydrateEndedCodesFromStorage()
  const key = normalizeMindmateCollabCode(code)
  const markedAt = recentlyEndedCodes.get(key)
  if (markedAt == null) {
    return false
  }
  if (Date.now() - markedAt > ENDED_CODE_TTL_MS) {
    recentlyEndedCodes.delete(key)
    persistEndedCodes()
    return false
  }
  return true
}

export interface LocalMindmateCollabSession {
  session_id: string
  code: string
  title: string
  owner_name?: string | null
  owner_user_id?: number
  participant_count?: number
  visibility?: string
  expires_at?: string | null
}

function notifySessionsChanged(): void {
  if (typeof window === 'undefined') {
    return
  }
  window.dispatchEvent(new CustomEvent(MINDMATE_COLLAB_SESSIONS_CHANGED_EVENT))
}

function migrateLegacySessionStorage(): void {
  if (typeof window === 'undefined') {
    return
  }
  try {
    const legacy = sessionStorage.getItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
    if (!legacy || localStorage.getItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)) {
      return
    }
    localStorage.setItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY, legacy)
    sessionStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
  } catch {
    // ignore quota / privacy mode
  }
}

export function normalizeMindmateCollabCode(code: string): string {
  return code.replace(/-/g, '').toUpperCase()
}

export function formatMindmateCollabCode(code: string): string {
  const raw = normalizeMindmateCollabCode(code)
  if (raw.length !== 6) {
    return code
  }
  return `${raw.slice(0, 3)}-${raw.slice(3, 6)}`
}

export function loadLocalMindmateCollabSessions(): LocalMindmateCollabSession[] {
  migrateLegacySessionStorage()
  try {
    const raw = localStorage.getItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
    if (!raw) {
      return []
    }
    return JSON.parse(raw) as LocalMindmateCollabSession[]
  } catch {
    return []
  }
}

export function persistLocalMindmateCollabSessions(rows: LocalMindmateCollabSession[]): void {
  try {
    localStorage.setItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY, JSON.stringify(rows))
    notifySessionsChanged()
  } catch {
    // quota exceeded or private browsing — skip persist
  }
}

export function mergeMindmateCollabSessionLists<T extends { code: string }>(
  orgSessions: T[],
  localSessions: T[],
): T[] {
  const byCode = new Map<string, T>()
  for (const row of orgSessions) {
    byCode.set(normalizeMindmateCollabCode(row.code), row)
  }
  for (const row of localSessions) {
    const key = normalizeMindmateCollabCode(row.code)
    if (!byCode.has(key)) {
      byCode.set(key, row)
    }
  }
  return Array.from(byCode.values())
}

export function trackLocalMindmateCollabSession(row: LocalMindmateCollabSession): void {
  if (wasMindmateCollabCodeRecentlyEnded(row.code)) {
    return
  }
  const key = normalizeMindmateCollabCode(row.code)
  const existing = loadLocalMindmateCollabSessions()
  const next = [row, ...existing.filter((s) => normalizeMindmateCollabCode(s.code) !== key)]
  persistLocalMindmateCollabSessions(next.slice(0, 10))
}

export function shouldReconnectMindmateCollab(code: number): boolean {
  if (code === 4010 || code === 4011 || code === 4003 || code === 1008 || code === 4029) {
    return false
  }
  return code !== 1000
}
