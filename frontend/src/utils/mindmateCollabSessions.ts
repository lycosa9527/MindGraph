/**
 * Local MindMate collab session tracking (sidebar rejoin list).
 *
 * Persisted in localStorage so public (network) rooms survive tab refresh.
 */

export const LOCAL_MINDMATE_COLLAB_SESSIONS_KEY = 'mindmate_collab_recent_sessions'
export const MINDMATE_COLLAB_SESSIONS_CHANGED_EVENT = 'mindmate-collab-sessions-changed'

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

export function trackLocalMindmateCollabSession(row: LocalMindmateCollabSession): void {
  const key = normalizeMindmateCollabCode(row.code)
  const existing = loadLocalMindmateCollabSessions()
  const next = [row, ...existing.filter((s) => normalizeMindmateCollabCode(s.code) !== key)]
  persistLocalMindmateCollabSessions(next.slice(0, 10))
}

export function shouldReconnectMindmateCollab(code: number): boolean {
  if (code === 4010 || code === 4011 || code === 4003) {
    return false
  }
  return code !== 1000
}
