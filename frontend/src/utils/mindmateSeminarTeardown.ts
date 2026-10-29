/**
 * Client-side MindMate collab session teardown (live UI state + optional history removal).
 */
import {
  embeddedCollabRoomCode,
  forgetJoinedCollabRoom,
  setEmbeddedCollabRoomCode,
} from '@/composables/mindmate/mindmateSeminarEmbeddedBridge'
import { authFetch } from '@/utils/api'
import {
  MINDMATE_COLLAB_SESSION_REMOVED_EVENT,
  loadLocalMindmateSeminarSessions,
  markMindmateSeminarCodeEnded,
  normalizeMindmateSeminarCode,
  persistLocalMindmateSeminarSessions,
} from '@/utils/mindmateSeminarSessions'

export interface MindmateSeminarTeardownOptions {
  /** Remove sidebar rejoin entry (host stop or room ended). Default false — keep for rejoin. */
  removeFromHistory?: boolean
}

export function removeLocalMindmateSeminarSessionByCode(code: string | null | undefined): void {
  if (!code) {
    return
  }
  const key = normalizeMindmateSeminarCode(code)
  markMindmateSeminarCodeEnded(key)
  const next = loadLocalMindmateSeminarSessions().filter(
    (row) => normalizeMindmateSeminarCode(row.code) !== key
  )
  persistLocalMindmateSeminarSessions(next)
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent(MINDMATE_COLLAB_SESSION_REMOVED_EVENT, { detail: { code: key } })
    )
  }
}

export function resolveMindmateSeminarSessionId(
  sessionId: string | null | undefined,
  code: string | null | undefined
): string | null {
  if (sessionId) {
    return sessionId
  }
  if (!code) {
    return null
  }
  const key = normalizeMindmateSeminarCode(code)
  const row = loadLocalMindmateSeminarSessions().find(
    (item) => normalizeMindmateSeminarCode(item.code) === key
  )
  return row?.session_id ?? null
}

/**
 * Session to archive when a room ends.
 * Ignores an id that belongs to a different invite code, so leaving a bad
 * sidebar row does not try to save the seminar that is still open.
 */
export function resolveEndedMindmateSeminarSessionId(
  sessionId: string | null | undefined,
  code: string | null | undefined
): string | null {
  const key = code ? normalizeMindmateSeminarCode(code) : ''
  const hinted = (sessionId || '').trim()
  if (hinted && key) {
    const hintedRow = loadLocalMindmateSeminarSessions().find((item) => item.session_id === hinted)
    if (hintedRow && normalizeMindmateSeminarCode(hintedRow.code) !== key) {
      return resolveMindmateSeminarSessionId('', code)
    }
  }
  return resolveMindmateSeminarSessionId(sessionId, code)
}

/** Release the embedded room pointer without dropping sidebar rejoin history. */
export function releaseMindmateSeminarClientState(code?: string | null): void {
  const current = embeddedCollabRoomCode.value
  if (
    code &&
    current &&
    normalizeMindmateSeminarCode(current) !== normalizeMindmateSeminarCode(code)
  ) {
    return
  }
  setEmbeddedCollabRoomCode(null)
}

/** Tear down live client state; optionally drop sidebar history when the room is finished. */
export function teardownMindmateSeminarClient(
  code: string | null | undefined,
  options: MindmateSeminarTeardownOptions = {}
): void {
  if (options.removeFromHistory && code) {
    removeLocalMindmateSeminarSessionByCode(code)
    forgetJoinedCollabRoom(code)
  }
  releaseMindmateSeminarClientState(code)
}

export function mindmateSeminarStopSucceeded(status: number): boolean {
  return (status >= 200 && status < 300) || status === 404
}

export async function requestMindmateSeminarLeave(sessionId: string): Promise<boolean> {
  try {
    const response = await authFetch('/api/mindmate/seminar/leave', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
    return response.ok
  } catch {
    return false
  }
}

export async function requestMindmateSeminarStop(sessionId: string): Promise<boolean> {
  try {
    const response = await authFetch('/api/mindmate/seminar/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
    return mindmateSeminarStopSucceeded(response.status)
  } catch {
    return false
  }
}

export function shouldRemoveCollabFromHistory(reason: 'expired' | 'host' | 'left'): boolean {
  return reason === 'expired' || reason === 'host'
}
