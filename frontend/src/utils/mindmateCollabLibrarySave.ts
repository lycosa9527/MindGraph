/**
 * Ending a seminar stores the full transcript in the owner's MindMate library.
 */
import router from '@/router'
import { authFetch } from '@/utils/api'

export const MINDMATE_COLLAB_LIBRARY_CHANGED_EVENT = 'mindmate-collab-library-changed'

export type SeminarLibrarySaveOutcome = 'saved' | 'failed' | 'joined'

const savesInFlight = new Map<string, Promise<Exclude<SeminarLibrarySaveOutcome, 'joined'>>>()
const savedSessionIds = new Set<string>()

export interface MindmateCollabLibraryChangeDetail {
  sessionId?: string
  title?: string
}

export function notifyMindmateCollabLibraryChanged(
  detail?: MindmateCollabLibraryChangeDetail
): void {
  if (typeof window === 'undefined') {
    return
  }
  window.dispatchEvent(new CustomEvent(MINDMATE_COLLAB_LIBRARY_CHANGED_EVENT, { detail }))
}

/** True when the owner ended the room (not when it only went idle or a guest left). */
export function shouldAutoSaveSeminarOnOwnerEnd(
  reason: 'idle' | 'host' | 'left',
  isOwner: boolean
): boolean {
  return isOwner && reason === 'host'
}

export function openSavedMindmateSeminar(sessionId: string): void {
  const id = sessionId.trim()
  if (!id) {
    return
  }
  void router.push({ path: '/mindmate', query: { saved_seminar: id } })
}

async function requestSaveFinishedSeminar(sessionId: string): Promise<boolean> {
  try {
    const response = await authFetch(
      `/api/mindmate/collab/${encodeURIComponent(sessionId)}/library`,
      { method: 'POST' }
    )
    return response.ok
  } catch {
    return false
  }
}

async function saveFinishedSeminarOnce(
  sessionId: string,
  openAfterSave: boolean
): Promise<Exclude<SeminarLibrarySaveOutcome, 'joined'>> {
  const saved = await requestSaveFinishedSeminar(sessionId)
  if (!saved) {
    return 'failed'
  }
  savedSessionIds.add(sessionId)
  notifyMindmateCollabLibraryChanged()
  if (openAfterSave) {
    openSavedMindmateSeminar(sessionId)
  }
  return 'saved'
}

/** Persist a finished seminar. Repeated calls for the same room share one request. */
export function saveFinishedSeminar(
  sessionId: string,
  options: { openAfterSave?: boolean } = {}
): Promise<SeminarLibrarySaveOutcome> {
  const id = sessionId.trim()
  if (!id) {
    return Promise.resolve('failed')
  }
  if (savedSessionIds.has(id)) {
    return Promise.resolve('joined')
  }
  const existing = savesInFlight.get(id)
  if (existing) {
    return existing.then((outcome) => (outcome === 'failed' ? 'failed' : 'joined'))
  }
  const task = saveFinishedSeminarOnce(id, options.openAfterSave !== false)
  savesInFlight.set(id, task)
  void task.finally(() => {
    if (savesInFlight.get(id) === task) {
      savesInFlight.delete(id)
    }
  })
  return task
}
