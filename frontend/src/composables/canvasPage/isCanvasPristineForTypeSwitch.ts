import type { useDiagramStore } from '@/stores/diagram'
import type { useLLMResultsStore } from '@/stores/llmResults'
import type { useSavedDiagramsStore } from '@/stores/savedDiagrams'

type DiagramStore = ReturnType<typeof useDiagramStore>
type SavedDiagramsStore = ReturnType<typeof useSavedDiagramsStore>
type LlmResultsStore = ReturnType<typeof useLLMResultsStore>

/**
 * True when the canvas is still the default template with no user/collab/library binding.
 * Safe to switch diagram type without a confirmation dialog.
 */
export function isCanvasPristineForTypeSwitch(
  diagramStore: DiagramStore,
  savedDiagramsStore: SavedDiagramsStore,
  llmResultsStore?: LlmResultsStore
): boolean {
  if (diagramStore.collabSessionActive) return false
  if (diagramStore.sessionEditCount > 0) return false
  const activeId = savedDiagramsStore.activeDiagramId?.trim() ?? ''
  if (activeId.length > 0) return false
  if (llmResultsStore?.isGenerating) return false
  if (llmResultsStore && llmResultsStore.successCount > 0) return false
  return true
}
