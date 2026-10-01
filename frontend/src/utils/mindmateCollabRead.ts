/**
 * Seminar read receipts.
 *
 * One cursor per person is the newest line they have seen. A line is read
 * when someone else's cursor is at or past that line.
 */

export interface CollabReadCursor {
  userId: number
  username: string
  lastReadMessageId: number
  readAt: string
}

export type CollabReceipt = 'sending' | 'sent' | 'read'

export function collabFrameCreatedAt(raw: unknown): string | undefined {
  if (typeof raw !== 'string') {
    return undefined
  }
  const trimmed = raw.trim()
  return trimmed || undefined
}

export function formatCollabMessageStamp(iso: string | undefined, now = new Date()): string {
  if (!iso) {
    return ''
  }
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  const time = new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
  if (date.toDateString() === now.toDateString()) {
    return time
  }
  const day = new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
  }).format(date)
  return `${day} ${time}`
}

export function collabReadCursorFromFrame(
  parsed: Record<string, unknown>
): CollabReadCursor | null {
  const userId = parsed.user_id
  const lastRead = parsed.last_read_message_id
  if (typeof userId !== 'number' || !Number.isInteger(userId) || userId <= 0) {
    return null
  }
  if (typeof lastRead !== 'number' || !Number.isInteger(lastRead) || lastRead <= 0) {
    return null
  }
  const rawName = parsed.username
  const username = typeof rawName === 'string' && rawName.trim() ? rawName.trim() : String(userId)
  const readAt = typeof parsed.read_at === 'string' ? parsed.read_at : ''
  return { userId, username, lastReadMessageId: lastRead, readAt }
}

export function applyCollabReadCursor(
  current: readonly CollabReadCursor[],
  incoming: CollabReadCursor
): CollabReadCursor[] {
  const existing = current.find((row) => row.userId === incoming.userId)
  if (existing && existing.lastReadMessageId > incoming.lastReadMessageId) {
    return [...current]
  }
  return [...current.filter((row) => row.userId !== incoming.userId), incoming]
}

export function applyCollabReadCursorList(
  current: readonly CollabReadCursor[],
  raw: unknown
): CollabReadCursor[] {
  if (!Array.isArray(raw)) {
    return [...current]
  }
  let next = [...current]
  for (const item of raw) {
    if (!item || typeof item !== 'object') {
      continue
    }
    const cursor = collabReadCursorFromFrame(item as Record<string, unknown>)
    if (cursor) {
      next = applyCollabReadCursor(next, cursor)
    }
  }
  return next
}

/** Other people whose cursor already covers this line. */
export function readersForCollabMessage(
  cursors: readonly CollabReadCursor[],
  messageId: number | undefined,
  senderUserId: number | null | undefined
): CollabReadCursor[] {
  if (messageId == null) {
    return []
  }
  return cursors
    .filter((row) => row.userId !== senderUserId && row.lastReadMessageId >= messageId)
    .sort((left, right) => left.username.localeCompare(right.username))
}

export function collabReceiptState(
  messageId: number | undefined,
  readerCount: number
): CollabReceipt {
  if (messageId == null) {
    return 'sending'
  }
  if (readerCount > 0) {
    return 'read'
  }
  return 'sent'
}
