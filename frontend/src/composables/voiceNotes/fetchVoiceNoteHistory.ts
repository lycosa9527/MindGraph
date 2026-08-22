/**
 * Voice Notes history uses the diagram library with a server-side
 * source_channel filter so MindGraph's cached list is never overwritten.
 */
import { voiceNotesHistoryListUrl } from '@/composables/voiceNotes/mobileVoiceNotesFinish'
import type { DiagramListResponse, SavedDiagram } from '@/stores/savedDiagrams'
import { authFetch } from '@/utils/api'

export async function fetchVoiceNoteHistoryDiagrams(
  pageSize: number = 50
): Promise<SavedDiagram[]> {
  const collected: SavedDiagram[] = []
  let page = 1
  let hasMore = true
  let total = Number.POSITIVE_INFINITY

  while (hasMore && collected.length < total) {
    const response = await authFetch(voiceNotesHistoryListUrl(page, pageSize))
    if (!response.ok) {
      throw new Error(`Failed to fetch voice note history: ${response.status}`)
    }
    const data: DiagramListResponse = await response.json()
    if (data.diagrams.length === 0) {
      break
    }
    collected.push(...data.diagrams)
    total = data.total
    hasMore = data.has_more
    page += 1
  }

  return collected
}
