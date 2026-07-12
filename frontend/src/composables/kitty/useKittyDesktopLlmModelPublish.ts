/**
 * Publish selected LLM over Kitty scope (desktop ↔ mobile).
 * PUT updates live_spec + peer clients; backend also fans out desktop SSE wake.
 */
import { type ComputedRef, type Ref, watch } from 'vue'

import { useLLMResultsStore } from '@/stores/llmResults'

export function useKittyDesktopLlmModelPublish(options: {
  enabled: ComputedRef<boolean>
  scopeId: Ref<string | null> | ComputedRef<string | null>
}): void {
  const llmResultsStore = useLLMResultsStore()
  let lastPostedKey = ''
  let inFlight: Promise<void> | null = null

  async function postModel(scope: string, model: string | null): Promise<void> {
    const key = `${scope}:${model ?? ''}`
    if (key === lastPostedKey) {
      return
    }
    try {
      const res = await fetch(`/api/kitty/llm_model/${encodeURIComponent(scope)}`, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected_llm_model: model }),
      })
      if (res.ok) {
        lastPostedKey = key
      }
    } catch {
      /* ignore transient network errors */
    }
  }

  function schedule(): void {
    if (!options.enabled.value) {
      lastPostedKey = ''
      return
    }
    const scope = options.scopeId.value?.trim() ?? ''
    if (!scope) {
      return
    }
    const model = llmResultsStore.selectedModel
    const run = async (): Promise<void> => {
      await postModel(scope, model)
    }
    if (inFlight != null) {
      inFlight = inFlight.then(run, run)
      return
    }
    inFlight = run().finally(() => {
      inFlight = null
    })
  }

  watch(
    () =>
      [
        options.enabled.value,
        options.scopeId.value,
        llmResultsStore.selectedModel,
      ] as const,
    () => {
      schedule()
    },
    { immediate: true }
  )
}
