/**
 * Eagerly persist MindMate generate_dingtalk preview PNGs to IndexedDB so they
 * survive server temp_images cleanup even when the user never scrolls the bubble
 * into view or closes the tab before lazy MessageBubble resolution runs.
 */

import {
  hasGeneratedDiagramImage,
  parseMindmateDiagramLibraryId,
} from '@/utils/mindmateDiagramMeta'
import { resolveMindmateDiagramPreviewBlob } from '@/utils/mindmateDiagramPreviewResolve'

function diagramPreviewPageHost(): string | undefined {
  return typeof window !== 'undefined' ? window.location.host : undefined
}

/** Fire-and-forget IndexedDB warm for one assistant markdown payload. */
export function queueMindmateDiagramPreviewPersist(content: string): void {
  const text = (content || '').trim()
  if (!hasGeneratedDiagramImage(text)) {
    return
  }
  void resolveMindmateDiagramPreviewBlob({
    content: text,
    pageHost: diagramPreviewPageHost(),
    libraryDiagramId: parseMindmateDiagramLibraryId(text),
  })
}

/** Warm diagram previews for all assistant messages in a loaded conversation. */
export function queueMindmateDiagramPreviewsForMessages(
  threadMessages: ReadonlyArray<{ role: string; content: string }>
): void {
  for (const message of threadMessages) {
    if (message.role === 'assistant') {
      queueMindmateDiagramPreviewPersist(message.content)
    }
  }
}
