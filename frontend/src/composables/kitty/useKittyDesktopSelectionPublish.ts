/**
 * Publish canvas node selection over Kitty scope (desktop → mobile).
 * PUT updates live_spec + mobile WS; backend also fans out desktop SSE wake.
 */
import { type ComputedRef, type Ref, watch } from 'vue'

import { useDiagramStore } from '@/stores/diagram'

function selectionKey(nodes: string[]): string {
  return nodes.join('\u0001')
}

export function useKittyDesktopSelectionPublish(options: {
  enabled: ComputedRef<boolean>
  scopeId: Ref<string | null> | ComputedRef<string | null>
}): void {
  const diagramStore = useDiagramStore()
  let lastPostedKey = ''
  let inFlight: Promise<void> | null = null

  async function postSelection(scope: string, nodes: string[]): Promise<void> {
    const key = `${scope}:${selectionKey(nodes)}`
    if (key === lastPostedKey) {
      return
    }
    try {
      const res = await fetch(`/api/kitty/selection/${encodeURIComponent(scope)}`, {
        method: 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected_nodes: nodes }),
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
    const nodes = [...diagramStore.selectedNodes]
    const run = async (): Promise<void> => {
      await postSelection(scope, nodes)
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
        selectionKey(diagramStore.selectedNodes),
      ] as const,
    () => {
      schedule()
    },
    { immediate: true }
  )
}
