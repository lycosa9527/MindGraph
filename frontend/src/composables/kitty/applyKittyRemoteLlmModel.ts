/**
 * Apply remote Kitty LLM model choice onto desktop llmResults (+ switch when ready).
 */
import type { LLMModel } from '@/stores/llmResults'
import { useLLMResultsStore } from '@/stores/llmResults'

const VALID_MODELS = new Set<string>(['qwen', 'deepseek', 'doubao'])

export function normalizeKittyLlmModel(raw: unknown): LLMModel | null {
  if (raw == null) {
    return null
  }
  if (typeof raw !== 'string') {
    return null
  }
  const key = raw.trim().toLowerCase()
  if (key === '' || key === 'null' || key === 'none') {
    return null
  }
  if (!VALID_MODELS.has(key)) {
    return null
  }
  return key as LLMModel
}

/**
 * Sync desktop (or shared Pinia) to the Kitty-selected model.
 * Ready cache → switchToModel; otherwise setSelectedModel only.
 */
export async function applyKittyRemoteLlmModel(rawModel: unknown): Promise<boolean> {
  const llmResultsStore = useLLMResultsStore()
  const model = normalizeKittyLlmModel(rawModel)

  if (model == null) {
    if (llmResultsStore.selectedModel != null) {
      llmResultsStore.setSelectedModel(null)
      return true
    }
    return false
  }

  if (llmResultsStore.selectedModel === model && llmResultsStore.modelStates[model] !== 'ready') {
    return false
  }

  if (llmResultsStore.modelStates[model] === 'ready') {
    if (llmResultsStore.selectedModel === model) {
      return false
    }
    return llmResultsStore.switchToModel(model)
  }

  if (llmResultsStore.selectedModel === model) {
    return false
  }
  llmResultsStore.setSelectedModel(model)
  return true
}
