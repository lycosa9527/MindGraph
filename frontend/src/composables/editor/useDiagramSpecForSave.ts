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

function attachLlmResultsIfFit(
  base: Record<string, unknown>,
  llmResultsStore: ReturnType<typeof useLLMResultsStore>
): Record<string, unknown> {
  const persisted = llmResultsStore.getResultsForPersistence()
  if (!persisted) return base

  const withLlm = { ...base, llm_results: persisted }
  const sizeKB = new Blob([JSON.stringify(withLlm)]).size / 1024
  return sizeKB <= SAVE.MAX_SPEC_SIZE_KB ? withLlm : base
}

/**
 * Pure diagram spec for export, previews, and templates.
 * Includes llm_results when 2+ successful LLM results fit under the size limit.
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
 */
export function useDiagramSpecForPersist(): () => Record<string, unknown> | null {
  const diagramStore = useDiagramStore()
  const llmResultsStore = useLLMResultsStore()

  return function getDiagramSpecForPersist(): Record<string, unknown> | null {
    const base = diagramStore.getSpecForSave()
    if (!base) return null
    llmResultsStore.updateCurrentModelSpec(base)
    return attachLlmResultsIfFit(base, llmResultsStore)
  }
}
