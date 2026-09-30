/**
 * Seminar transcript gap check.
 *
 * Each saved line carries the previous line's id in that room. If the client
 * does not have that previous id, it asks the server for the rows in between.
 */

export interface CollabGapRow {
  id?: number
  role: 'user' | 'assistant'
  content: string
}

export function collabPrevId(raw: unknown): number | null {
  if (typeof raw !== 'number' || !Number.isInteger(raw) || raw <= 0) {
    return null
  }
  return raw
}

export const COLLAB_HISTORY_SYNC_PAGES = 20

export function collabChainNeedsFill(
  messages: readonly { id?: number }[],
  prevId: number | null
): boolean {
  if (prevId == null) {
    return false
  }
  return !messages.some((row) => row.id === prevId)
}

export function collabMaxSavedId(messages: readonly { id?: number }[]): number {
  let maxId = 0
  for (const row of messages) {
    if (row.id != null && row.id > maxId) {
      maxId = row.id
    }
  }
  return maxId
}

/** True when the server head is a saved line this screen does not have yet. */
export function collabCursorBehind(
  messages: readonly { id?: number }[],
  latestId: number | null
): boolean {
  return collabChainNeedsFill(messages, latestId)
}

/**
 * When a reconnect snapshot starts after lines this screen already had,
 * return that cursor so the hole in between can be loaded.
 */
export function collabSnapshotBackfillAfterId(
  priorMaxId: number,
  snapshotRows: readonly { id?: number }[]
): number | null {
  let snapshotMin = 0
  for (const row of snapshotRows) {
    if (row.id != null && (snapshotMin === 0 || row.id < snapshotMin)) {
      snapshotMin = row.id
    }
  }
  if (priorMaxId <= 0 || snapshotMin <= 0 || snapshotMin <= priorMaxId) {
    return null
  }
  return priorMaxId
}

/** Highest saved id strictly below the missing link, used as history `after_id`. */
export function collabGapAfterId(messages: readonly { id?: number }[], prevId: number): number {
  let below = 0
  for (const row of messages) {
    if (row.id != null && row.id < prevId && row.id > below) {
      below = row.id
    }
  }
  return below
}

function savedUserKey(row: { sender_user_id?: number | null; content?: string }): string {
  return `${row.sender_user_id ?? ''}:${row.content ?? ''}`
}

export function insertMissingCollabMessages<
  T extends {
    id?: number
    role?: string
    content?: string
    sender_user_id?: number | null
    clientKey?: string
  },
>(current: readonly T[], incoming: readonly T[]): T[] {
  const have = new Set<number>()
  for (const row of current) {
    if (row.id != null) {
      have.add(row.id)
    }
  }
  const missing = incoming.filter((row) => row.id != null && !have.has(row.id))
  const numbered = current.filter((row) => row.id != null)
  const savedKeys = new Set<string>()
  for (const row of [...numbered, ...missing]) {
    if (row.id != null && row.role === 'user') {
      savedKeys.add(savedUserKey(row))
    }
  }
  const tail = current.filter((row) => {
    if (row.id != null) {
      return false
    }
    if (row.role === 'user' && row.clientKey && savedKeys.has(savedUserKey(row))) {
      return false
    }
    return true
  })
  if (missing.length === 0 && tail.length === current.filter((row) => row.id == null).length) {
    return [...current]
  }
  const merged = [...numbered, ...missing].sort((left, right) => (left.id ?? 0) - (right.id ?? 0))
  return [...merged, ...tail]
}

export function streamingCoveredBySaved(
  streamContent: string,
  incoming: readonly CollabGapRow[]
): boolean {
  return incoming.some(
    (row) =>
      row.role === 'assistant' &&
      row.id != null &&
      (row.content === streamContent ||
        (streamContent.length > 0 && row.content.startsWith(streamContent)))
  )
}
