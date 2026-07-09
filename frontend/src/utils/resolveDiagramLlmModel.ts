/** Canvas LLM keys aligned with AIModelSelector / llmResults store. */
export const CANVAS_LLM_MODELS = ['qwen', 'deepseek', 'doubao'] as const

export type CanvasLlmModel = (typeof CANVAS_LLM_MODELS)[number]

const CANVAS_LLM_SET = new Set<string>(CANVAS_LLM_MODELS)

/** Resolve the active canvas LLM from user selection (defaults to qwen). */
export function resolveDiagramLlmModel(selected: string | null | undefined): CanvasLlmModel {
  const key = (selected ?? '').trim().toLowerCase()
  if (CANVAS_LLM_SET.has(key)) {
    return key as CanvasLlmModel
  }
  return 'qwen'
}
