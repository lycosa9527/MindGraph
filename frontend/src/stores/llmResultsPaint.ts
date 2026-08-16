/**
 * Auto-complete paint / persist guards for multi-LLM results.
 * Generation session is the source of truth — not selectedModel leftovers.
 */

/** Drop completions / errors that belong to a superseded generate round. */
export function isLlmResultForCurrentSession(
  activeSessionId: string | null,
  resultSessionId: string | null | undefined
): boolean {
  if (!activeSessionId) {
    return false
  }
  if (resultSessionId == null) {
    return true
  }
  return activeSessionId === resultSessionId
}

/**
 * First success of this round always paints (first-result-wins).
 * Later completions only refresh the model already on the canvas.
 */
export function shouldPaintCompletedLlmModel(options: {
  paintedModel: string | null
  selectedModel: string | null
  completedModel: string
}): boolean {
  if (options.paintedModel === null) {
    return true
  }
  return options.selectedModel === options.completedModel
}

/**
 * Never stamp the live canvas onto a model cache while generate is in flight.
 * The first finisher's persist/nextTick snapshot is often still the previous
 * diagram (专业程度 regenerate), which clobbers that model's new spec.
 */
export function shouldStampCanvasOntoLlmResult(options: {
  isGenerating: boolean
  selectedModel: string | null
}): boolean {
  if (!options.selectedModel) {
    return false
  }
  return !options.isGenerating
}
