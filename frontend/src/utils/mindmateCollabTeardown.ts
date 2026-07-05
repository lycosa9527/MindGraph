/**
 * Client-side MindMate collab session teardown (live UI state + optional history removal).
 */
import { setEmbeddedCollabRoomCode } from '@/composables/mindmate/mindmateCollabEmbeddedBridge'
import { clearMindmateCollabPresenceSnapshot } from '@/composables/mindmate/mindmateCollabPresenceBridge'
import { authFetch } from '@/utils/api'
import {
  loadLocalMindmateCollabSessions,
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
  const next = loadLocalMindmateCollabSessions().filter(
    (row) => normalizeMindmateCollabCode(row.code) !== key,
  )
  persistLocalMindmateCollabSessions(next)
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

/** Release embedded bridge and presence without dropping sidebar rejoin history. */
export function releaseMindmateCollabClientState(): void {
  setEmbeddedCollabRoomCode(null)
  clearMindmateCollabPresenceSnapshot()
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

export async function requestMindmateCollabStop(sessionId: string): Promise<boolean> {
  try {
    const response = await authFetch('/api/mindmate/collab/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
    return response.ok
  } catch {
    return false
  }
}

export function shouldRemoveCollabFromHistory(reason: 'idle' | 'host' | 'left'): boolean {
  return reason === 'idle' || reason === 'host'
}
