/**
 * When mobile Kitty is paired on this canvas, publish Pinia diagram into live_spec
 * so the phone can hydrate manual desktop edits.
 */
import { type ComputedRef, type Ref, watch } from 'vue'

import { getKittyDiagramContentFingerprint } from '@/composables/kitty/kittyDiagramFingerprint'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'

const DEBOUNCE_MS = 700

export function useKittyDesktopLiveSpecPublish(options: {
  enabled: ComputedRef<boolean>
  scopeId: Ref<string | null> | ComputedRef<string | null>
}): void {
  const diagramStore = useDiagramStore()
  const llmResultsStore = useLLMResultsStore()
  let lastPostedKey = ''
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let inFlight: Promise<void> | null = null

  async function postSnapshot(scope: string): Promise<void> {
    const diagramType = diagramStore.type
    const data = diagramStore.data
    if (diagramType == null || data == null) {
      return
    }
    const fingerprint = getKittyDiagramContentFingerprint(data)
    const selKey = diagramStore.selectedNodes.join('\u0001')
    const key = `${scope}:${fingerprint}:${selKey}:${llmResultsStore.selectedModel ?? ''}`
    if (key === lastPostedKey || fingerprint === '') {
      return
    }
    try {
      const res = await fetch(`/api/kitty/live_context/${encodeURIComponent(scope)}`, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          diagram_type: diagramType,
          diagram_data: {
            nodes: data.nodes ?? [],
            connections: data.connections ?? [],
          },
          selected_nodes: [...diagramStore.selectedNodes],
          active_panel: 'one_sentence',
          selected_llm_model: llmResultsStore.selectedModel,
        }),
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
      if (debounceTimer != null) {
        clearTimeout(debounceTimer)
        debounceTimer = null
      }
      return
    }
    const scope = options.scopeId.value?.trim() ?? ''
    if (!scope) {
      return
    }
    if (debounceTimer != null) {
      clearTimeout(debounceTimer)
    }
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      const run = async (): Promise<void> => {
        await postSnapshot(scope)
      }
      if (inFlight != null) {
        inFlight = inFlight.then(run, run)
        return
      }
      inFlight = run().finally(() => {
        inFlight = null
      })
    }, DEBOUNCE_MS)
  }

  watch(
    () =>
      [
        options.enabled.value,
        options.scopeId.value,
        getKittyDiagramContentFingerprint(diagramStore.data),
        diagramStore.selectedNodes.join('\u0001'),
        llmResultsStore.selectedModel,
      ] as const,
    () => {
      schedule()
    },
    { immediate: true }
  )
}
