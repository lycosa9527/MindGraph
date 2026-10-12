/**
 * Live canvas model ids from /api/config/canvas-llm-models.
 * Defaults match env.example until the server answers, so the menu does not
 * flash the short marketing names.
 */
import { ref } from 'vue'

import { apiRequestJson } from '@/utils/apiClient'

export const CANVAS_LLM_MODEL_DEFAULTS: Readonly<Record<string, string>> = {
  express: 'deepseek-v4.1-flash',
  'qwen3.8-flash': 'qwen3.8-flash',
  'qwen3-max': 'qwen3.8-max',
  kimi: 'glm-5-3-flash-260828',
  doubao21: 'doubao-seed-2-1-turbo-260628',
}

const names = ref<Record<string, string>>({ ...CANVAS_LLM_MODEL_DEFAULTS })
let loadPromise: Promise<void> | null = null

interface CanvasLlmModelsPayload {
  models?: Record<string, unknown>
}

function applyPayload(models: Record<string, unknown> | undefined): void {
  if (!models) {
    return
  }
  const next: Record<string, string> = {}
  for (const [key, value] of Object.entries(models)) {
    if (typeof value === 'string' && value.trim()) {
      next[key] = value.trim()
    }
  }
  names.value = next
}

async function loadCanvasLlmModelNames(): Promise<void> {
  try {
    const data = await apiRequestJson<CanvasLlmModelsPayload>('/api/config/canvas-llm-models')
    applyPayload(data.models)
  } catch (error) {
    loadPromise = null
    console.error('[CanvasLlm] model names', error)
  }
}

export function useCanvasLlmModelNames(): { names: typeof names } {
  if (!loadPromise) {
    loadPromise = loadCanvasLlmModelNames()
  }
  return { names }
}
