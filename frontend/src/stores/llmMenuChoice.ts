/**
 * Status-bar / Kitty model pick.
 * A model with a saved diagram replaces the canvas. Any other pick only
 * moves the menu, including on a diagram that has never run auto-complete.
 */
import { eventBus } from '@/composables/core/useEventBus'

import { useLLMResultsStore } from './llmResults'

export function requestLlmMenuPersist(): void {
  const store = useLLMResultsStore()
  if (store.isGenerating || !store.hasAnyResults) {
    return
  }
  eventBus.emit('llm:model_selection_clicked', {})
}

export async function selectCanvasLlmModel(model: string): Promise<boolean> {
  const store = useLLMResultsStore()
  if (store.isResultValid(model)) {
    const switched = await store.switchToModel(model)
    if (switched) {
      requestLlmMenuPersist()
      return true
    }
  }
  store.setSelectedModel(model)
  requestLlmMenuPersist()
  return false
}
