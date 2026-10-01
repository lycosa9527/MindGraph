/**
 * Load seminar lines the screen skipped, one page at a time.
 */
import { authFetch } from '@/utils/api'
import { COLLAB_HISTORY_SYNC_PAGES, insertMissingCollabMessages } from '@/utils/mindmateCollabGap'

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
        const data = (await response.json()) as { messages?: T[]; has_more?: boolean }
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
        if (data.has_more === false || rows.length < 200 || typeof lastId !== 'number') {
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

function oldestSavedId(messages: readonly { id?: number }[]): number {
  let oldest = 0
  for (const row of messages) {
    if (row.id != null && (oldest === 0 || row.id < oldest)) {
      oldest = row.id
    }
  }
  return oldest
}

/** Older seminar page, strictly before the oldest line already on screen. */
export async function pullMindmateCollabHistoryBefore<T extends { id?: number }>(
  sessionId: string,
  beforeId: number
): Promise<{ rows: T[]; hasMore: boolean } | null> {
  try {
    const response = await authFetch(
      `/api/mindmate/collab/${encodeURIComponent(sessionId)}/history?before_id=${beforeId}&limit=100`
    )
    if (!response.ok) {
      return null
    }
    const data = (await response.json()) as { messages?: T[]; has_more?: boolean }
    return {
      rows: Array.isArray(data.messages) ? data.messages : [],
      hasMore: data.has_more === true,
    }
  } catch {
    return null
  }
}

export async function loadOlderSeminarPage<
  T extends {
    id?: number
    role?: string
    content?: string
    sender_user_id?: number | null
    clientKey?: string
  },
>(sessionId: string, current: readonly T[]): Promise<{ messages: T[]; hasMore: boolean } | null> {
  const beforeId = oldestSavedId(current)
  if (!sessionId || beforeId <= 0) {
    return null
  }
  const page = await pullMindmateCollabHistoryBefore<T>(sessionId, beforeId)
  if (!page) {
    return null
  }
  return {
    messages: page.rows.length > 0 ? insertMissingCollabMessages(current, page.rows) : [...current],
    hasMore: page.hasMore && page.rows.length > 0,
  }
}
