import { type CanvasLlmModel, isCanvasLlmModel } from '@/config/canvasLlmMenu'

/** Canvas LLM keys. Express is the live default; older keys stay for saved diagrams. */
export { CANVAS_LLM_MODELS, type CanvasLlmModel, isCanvasLlmModel } from '@/config/canvasLlmMenu'

export const DEFAULT_CANVAS_LLM_MODEL: CanvasLlmModel = 'express'

/** Resolve the active canvas LLM from user selection (defaults to express). */
export function resolveDiagramLlmModel(selected: string | null | undefined): CanvasLlmModel {
  if (isCanvasLlmModel(selected)) {
    return selected
  }
  return DEFAULT_CANVAS_LLM_MODEL
}
