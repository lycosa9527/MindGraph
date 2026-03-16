/**
 * useDiagramSpecForSave - Get diagram spec for saving with optional LLM results
 *
 * When the diagram has 2+ LLM results, includes llm_results in the spec
 * so model switching persists when reopening from library.
 */
import { SAVE } from '@/config'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'

/**
 * Get diagram spec for saving.
 * Includes llm_results when we have 2+ successful LLM results (if under size limit).
 */
export function useDiagramSpecForSave(): () => Record<string, unknown> | null {
  const diagramStore = useDiagramStore()
  const llmResultsStore = useLLMResultsStore()

  return function getDiagramSpec(): Record<string, unknown> | null {
    const base = diagramStore.getSpecForSave()
    if (!base) return null

    const persisted = llmResultsStore.getResultsForPersistence()
    if (!persisted) return base

    const withLlm = { ...base, llm_results: persisted }
    const sizeKB = new Blob([JSON.stringify(withLlm)]).size / 1024
    return sizeKB <= SAVE.MAX_SPEC_SIZE_KB ? withLlm : base
  }
}
