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

export function collabChainNeedsFill(
  messages: readonly { id?: number }[],
  prevId: number | null
): boolean {
  if (prevId == null) {
    return false
  }
  return !messages.some((row) => row.id === prevId)
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

export function insertMissingCollabMessages<T extends { id?: number }>(
  current: readonly T[],
  incoming: readonly T[]
): T[] {
  const have = new Set<number>()
  for (const row of current) {
    if (row.id != null) {
      have.add(row.id)
    }
  }
  const missing = incoming.filter((row) => row.id != null && !have.has(row.id))
  if (missing.length === 0) {
    return [...current]
  }
  const numbered = current.filter((row) => row.id != null)
  const tail = current.filter((row) => row.id == null)
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
