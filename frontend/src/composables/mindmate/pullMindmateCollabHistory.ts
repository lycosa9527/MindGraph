/**
 * Load seminar lines the screen skipped, one page at a time.
 */
import { authFetch } from '@/utils/api'
import { COLLAB_HISTORY_SYNC_PAGES } from '@/utils/mindmateCollabGap'

export async function pullMindmateCollabHistory<T extends { id?: number }>(options: {
  sessionId: string
  startAfter: number
  stillCurrent: () => boolean
  gapFill: { current: Promise<void> | null }
  applyRows: (rows: T[]) => void
}): Promise<boolean> {
  if (!options.sessionId || !options.stillCurrent()) {
    return false
  }
  if (options.gapFill.current) {
    await options.gapFill.current
    if (!options.stillCurrent()) {
      return false
    }
  }
  const outcome = { ok: false }
  const run = (async () => {
    let cursor = options.startAfter
    try {
      for (let page = 0; page < COLLAB_HISTORY_SYNC_PAGES; page += 1) {
        if (!options.stillCurrent()) {
          return
        }
        const response = await authFetch(
          `/api/mindmate/collab/${encodeURIComponent(options.sessionId)}/history?after_id=${cursor}&limit=200`
        )
        if (!response.ok) {
          return
        }
        const data = (await response.json()) as { messages?: T[] }
        const rows = Array.isArray(data.messages) ? data.messages : []
        if (!options.stillCurrent()) {
          return
        }
        if (rows.length === 0) {
          outcome.ok = true
          return
        }
        options.applyRows(rows)
        const lastId = rows[rows.length - 1]?.id
        if (rows.length < 200 || typeof lastId !== 'number') {
          outcome.ok = true
          return
        }
        cursor = lastId
      }
      outcome.ok = true
    } catch {
      return
    }
  })()
  options.gapFill.current = run
  try {
    await run
  } finally {
    if (options.gapFill.current === run) {
      options.gapFill.current = null
    }
  }
  return outcome.ok
}
