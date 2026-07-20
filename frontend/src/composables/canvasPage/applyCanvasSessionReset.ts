import { clearCanvasEphemeralSession } from '@/composables/canvasPage/clearCanvasEphemeralSession'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore, useOneSentenceStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

/**
 * Abort in-flight AI streams and clear ephemeral Pinia state before reloading
 * the default template. CanvasPage listens for `diagram:reset_requested` to
 * reset page-local refs (presentation rail, snapshots, autosave suppress,
 * file-center session).
 */
export function applyCanvasSessionReset(): void {
  clearCanvasEphemeralSession()

  const diagramStore = useDiagramStore()
  diagramStore.clearSelection()
  diagramStore.clearHistory()
  diagramStore.clearCopiedNodes()
  diagramStore.resetSessionEditCount()

  const savedDiagrams = useSavedDiagramsStore()
  // Capture before clear — Document Summary COS cleanup needs the diagram id.
  const diagramId = savedDiagrams.activeDiagramId ?? undefined
  savedDiagrams.clearActiveDiagram()
  // Keep durable library chat in Redis/PG; rotate ephemeral UI scope.
  useOneSentenceStore().onCanvasReset()

  eventBus.emit('diagram:reset_requested', { diagramId })
}
