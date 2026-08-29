/**
 * Client-side MindMate collab session teardown (live UI state + optional history removal).
 */
import { setEmbeddedCollabRoomCode } from '@/composables/mindmate/mindmateCollabEmbeddedBridge'
import { authFetch } from '@/utils/api'
import {
  loadLocalMindmateCollabSessions,
  markMindmateCollabCodeEnded,
  MINDMATE_COLLAB_SESSION_REMOVED_EVENT,
  normalizeMindmateCollabCode,
  persistLocalMindmateCollabSessions,
} from '@/utils/mindmateCollabSessions'

export interface MindmateCollabTeardownOptions {
  /** Remove sidebar rejoin entry (host stop or room ended). Default false — keep for rejoin. */
  removeFromHistory?: boolean
}

export function removeLocalMindmateCollabSessionByCode(code: string | null | undefined): void {
  if (!code) {
    return
  }
  const key = normalizeMindmateCollabCode(code)
  markMindmateCollabCodeEnded(key)
  const next = loadLocalMindmateCollabSessions().filter(
    (row) => normalizeMindmateCollabCode(row.code) !== key,
  )
  persistLocalMindmateCollabSessions(next)
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent(MINDMATE_COLLAB_SESSION_REMOVED_EVENT, { detail: { code: key } }),
    )
  }
}

export function resolveMindmateCollabSessionId(
  sessionId: string | null | undefined,
  code: string | null | undefined,
): string | null {
  if (sessionId) {
    return sessionId
  }
  if (!code) {
    return null
  }
  const key = normalizeMindmateCollabCode(code)
  const row = loadLocalMindmateCollabSessions().find(
    (item) => normalizeMindmateCollabCode(item.code) === key,
  )
  return row?.session_id ?? null
}

/** Release the embedded room pointer without dropping sidebar rejoin history. */
export function releaseMindmateCollabClientState(): void {
  setEmbeddedCollabRoomCode(null)
}

/** Tear down live client state; optionally drop sidebar history when the room is finished. */
export function teardownMindmateCollabClient(
  code: string | null | undefined,
  options: MindmateCollabTeardownOptions = {},
): void {
  if (options.removeFromHistory) {
    removeLocalMindmateCollabSessionByCode(code)
  }
  releaseMindmateCollabClientState()
}

export function mindmateCollabStopSucceeded(status: number): boolean {
  return (status >= 200 && status < 300) || status === 404
}

export async function requestMindmateCollabStop(sessionId: string): Promise<boolean> {
  try {
    const response = await authFetch('/api/mindmate/collab/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
    return mindmateCollabStopSucceeded(response.status)
  } catch {
    return false
  }
}

export function shouldRemoveCollabFromHistory(reason: 'idle' | 'host' | 'left'): boolean {
  return reason === 'idle' || reason === 'host'
}
