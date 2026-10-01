import { isCanvasPristineForTypeSwitch } from '@/composables/canvasPage/isCanvasPristineForTypeSwitch'
import type { useDiagramStore } from '@/stores/diagram'
import type { useLLMResultsStore } from '@/stores/llmResults'
import type { useSavedDiagramsStore } from '@/stores/savedDiagrams'

type DiagramStore = ReturnType<typeof useDiagramStore>
type SavedDiagramsStore = ReturnType<typeof useSavedDiagramsStore>
type LlmResultsStore = ReturnType<typeof useLLMResultsStore>

function isMindMapType(diagramType: string | null | undefined): boolean {
  const norm = (diagramType ?? '').trim().toLowerCase()
  return norm === 'mindmap' || norm === 'mind_map'
}

/**
 * True when the canvas already has at least one non-topic branch node.
 */
export function isMindMapCanvasReadyForOneSentenceEdit(diagramStore: DiagramStore): boolean {
  if (!isMindMapType(diagramStore.type)) {
    return false
  }
  const nodes = diagramStore.data?.nodes ?? []
  if (nodes.length <= 1) {
    return false
  }
  return nodes.some((node) => {
    const id = (node.id ?? '').trim()
    const nodeType = (node.type ?? '').trim().toLowerCase()
    if (id === 'topic' || nodeType === 'topic' || nodeType === 'center') {
      return false
    }
    return Boolean((node.text ?? '').trim())
  })
}

/**
 * Route one-sentence chat to Kitty structural edits (not full LLM regen).
 */
export function shouldUseOneSentenceEditFlow(
  diagramStore: DiagramStore,
  savedDiagramsStore: SavedDiagramsStore,
  llmResultsStore: LlmResultsStore,
  phase: 'create' | 'edit'
): boolean {
  if (phase === 'edit') {
    return true
  }
  if (!isMindMapType(diagramStore.type)) {
    return false
  }
  if (!isCanvasPristineForTypeSwitch(diagramStore, savedDiagramsStore, llmResultsStore)) {
    return true
  }
  return isMindMapCanvasReadyForOneSentenceEdit(diagramStore)
}
