/**
 * Maite learning map — fetch graph on refresh request.
 */
import { onScopeDispose, ref } from 'vue'

import { getGraph } from '@/api/maite/map'
import { eventBus } from '@/composables/core/useEventBus'

import type { MaiteGraphResponse } from '@/types/maite'

export function useMaiteMap() {
  const loading = ref(false)
  const errorMessage = ref('')
  const graph = ref<MaiteGraphResponse | null>(null)

  async function refreshGraph(): Promise<void> {
    loading.value = true
    errorMessage.value = ''
    try {
      graph.value = await getGraph()
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'graph_failed'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'map_graph',
      })
    } finally {
      loading.value = false
    }
  }

  const offRefresh = eventBus.on('maite:map_refresh_requested', () => {
    void refreshGraph()
  })

  onScopeDispose(() => {
    offRefresh()
  })

  return {
    loading,
    errorMessage,
    graph,
    refreshGraph,
  }
}
