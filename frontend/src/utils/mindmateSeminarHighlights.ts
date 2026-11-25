/**
 * Shared seminar group highlights (精华).
 */
import { apiRequestJson } from '@/utils/apiClient'

/** Matches the seminar chat cap so a teaching-design reply is not cut mid-sentence. */
export const MAX_SEMINAR_HIGHLIGHT_TEXT = 65536

/**
 * Expand uses the live bubble when the pin is a truncated prefix of that message.
 * A selected excerpt that is not a prefix stays as-is.
 */
export function resolveSeminarHighlightBodyText(
  pinned: string,
  liveContent?: string | null
): string {
  const snapshot = pinned || ''
  const live = liveContent || ''
  if (!live.trim()) {
    return snapshot
  }
  if (!snapshot.trim()) {
    return live
  }
  if (live.length <= snapshot.length) {
    return snapshot
  }
  const snapStart = snapshot.trim()
  const liveCompact = live.replace(/\s+/g, '')
  const snapCompact = snapStart.replace(/\s+/g, '')
  if (live.startsWith(snapStart) || liveCompact.startsWith(snapCompact)) {
    return live
  }
  return snapshot
}

export interface SeminarHighlight {
  id: string
  text: string
  authorName: string
  messageId: number | null
  createdAt: string
  createdByUserId?: number | null
  createdByName?: string
  messageAt?: string
}

export interface SeminarHighlightRaw {
  id: string
  text: string
  author_name: string
  message_id: number | null
  created_at: string
  created_by_user_id?: number | null
  created_by_name?: string
  message_at?: string | null
}

export function mapSeminarHighlight(raw: SeminarHighlightRaw): SeminarHighlight {
  return {
    id: raw.id,
    text: raw.text,
    authorName: raw.author_name,
    messageId: typeof raw.message_id === 'number' ? raw.message_id : null,
    createdAt: raw.created_at,
    createdByUserId: typeof raw.created_by_user_id === 'number' ? raw.created_by_user_id : null,
    createdByName: raw.created_by_name || '',
    messageAt: raw.message_at || '',
  }
}

export function highlightDedupeKey(item: Pick<SeminarHighlight, 'messageId' | 'text'>): string {
  return `${item.messageId ?? ''}|${item.text}`
}

export function mergeSeminarHighlights(
  primary: SeminarHighlight[],
  extra: SeminarHighlight[]
): SeminarHighlight[] {
  const seenIds = new Set(primary.map((item) => item.id))
  const seenKeys = new Set(primary.map(highlightDedupeKey))
  const added = extra.filter((item) => {
    if (seenIds.has(item.id) || seenKeys.has(highlightDedupeKey(item))) {
      return false
    }
    seenIds.add(item.id)
    seenKeys.add(highlightDedupeKey(item))
    return true
  })
  return [...primary, ...added]
}

export async function listSeminarHighlightsApi(sessionId: string): Promise<SeminarHighlight[]> {
  const payload = await apiRequestJson<{ items: SeminarHighlightRaw[] }>(
    `/api/mindmate/seminar/highlights?session_id=${encodeURIComponent(sessionId)}`
  )
  return (payload.items || []).map(mapSeminarHighlight)
}

export async function createSeminarHighlightApi(
  sessionId: string,
  entry: {
    text: string
    authorName: string
    createdByName?: string
    messageId: number | null
    messageAt?: string
  }
): Promise<SeminarHighlight> {
  const payload = await apiRequestJson<SeminarHighlightRaw>('/api/mindmate/seminar/highlights', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      text: entry.text,
      author_name: entry.authorName,
      created_by_name: entry.createdByName || '',
      message_id: entry.messageId,
      message_at: entry.messageAt || null,
    }),
  })
  return mapSeminarHighlight(payload)
}

export async function deleteSeminarHighlightApi(
  sessionId: string,
  highlightId: string
): Promise<void> {
  await apiRequestJson(
    `/api/mindmate/seminar/highlights/${encodeURIComponent(highlightId)}?session_id=${encodeURIComponent(sessionId)}`,
    { method: 'DELETE' }
  )
}
