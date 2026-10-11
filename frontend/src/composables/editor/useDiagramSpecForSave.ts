/**
 * Build diagram specs for save / export, optionally including multi-model
 * ``llm_results``.
 *
 * ``useDiagramSpecForSave`` is a pure read — safe in Vue templates.
 * ``useDiagramSpecForPersist`` stamps the live canvas into the selected LLM
 * model slot first — call only from intentional save/flush paths.
 *
 * Never stamp from a template getter: mutating Pinia during render (e.g.
 * CanvasTopBar ``pending-spec``) causes an infinite re-render freeze.
 */
import { SAVE } from '@/config'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'
import { attachLlmResultsWithinSizeLimit } from '@/stores/llmResultsPersist'
import {
  getDiagramPersistBaseSpec,
  shouldStampLiveCanvasOntoLlmResult,
} from '@/utils/diagramPersistBaseSpec'

function attachLlmResultsIfFit(
  base: Record<string, unknown>,
  llmResultsStore: ReturnType<typeof useLLMResultsStore>
): Record<string, unknown> {
  return attachLlmResultsWithinSizeLimit(
    base,
    llmResultsStore.getResultsForPersistence(),
    SAVE.MAX_SPEC_WITH_LLM_RESULTS_KB
  )
}

/**
 * Pure diagram spec for export, previews, and templates.
 * A manual or single-model diagram is one spec. Several models are all included.
 */
export function useDiagramSpecForSave(): () => Record<string, unknown> | null {
  const diagramStore = useDiagramStore()
  const llmResultsStore = useLLMResultsStore()

  return function getDiagramSpec(): Record<string, unknown> | null {
    const base = diagramStore.getSpecForSave()
    if (!base) return null
    return attachLlmResultsIfFit(base, llmResultsStore)
  }
}

/**
 * Persist-path spec: stamp live canvas into the selected model slot, then build.
 * While a translate preview is on the canvas, persist the original snapshot.
 */
export function useDiagramSpecForPersist(): () => Record<string, unknown> | null {
  const llmResultsStore = useLLMResultsStore()

  return function getDiagramSpecForPersist(): Record<string, unknown> | null {
    const base = getDiagramPersistBaseSpec()
    if (!base) return null
    if (shouldStampLiveCanvasOntoLlmResult()) {
      llmResultsStore.updateCurrentModelSpec(base)
    }
    return attachLlmResultsIfFit(base, llmResultsStore)
  }
}
