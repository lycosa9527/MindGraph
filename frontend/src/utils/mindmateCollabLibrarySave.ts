/**
 * Ending a seminar stores the full transcript in the owner's MindMate library.
 */
import router from '@/router'
import { authFetch } from '@/utils/api'
import { releaseMindmateCollabClientState } from '@/utils/mindmateCollabTeardown'

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

export function isStandaloneMindmateCollabPath(path: string): boolean {
  return path === '/mindmate/collab' || path.startsWith('/mindmate/collab/')
}

export function openSavedMindmateSeminar(sessionId: string): void {
  const id = sessionId.trim()
  if (!id) {
    return
  }
  releaseMindmateCollabClientState()
  void router.push({ path: '/mindmate', query: { saved_seminar: id } })
}

/** Drop `saved_seminar` so a personal thread can replace the read-only transcript. */
export function withoutSavedSeminarQuery<T extends Record<string, unknown>>(
  query: T
): T | null {
  if (typeof query.saved_seminar !== 'string') {
    return null
  }
  const nextQuery = { ...query }
  delete nextQuery.saved_seminar
  return nextQuery
}

/** Leave a saved seminar opened from the sidebar library. */
export function leaveSavedMindmateSeminar(): void {
  const nextQuery = withoutSavedSeminarQuery(router.currentRoute.value.query)
  if (!nextQuery) {
    return
  }
  void router.replace({ query: nextQuery })
}

/**
 * Show a personal MindMate thread.
 * Drops the saved-seminar transcript and the embedded live room view.
 * A live room stays in the sidebar so it can be rejoined.
 */
export function focusPersonalMindmateThread(): void {
  releaseMindmateCollabClientState()
  if (isStandaloneMindmateCollabPath(router.currentRoute.value.path)) {
    void router.push('/mindmate')
    return
  }
  leaveSavedMindmateSeminar()
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
