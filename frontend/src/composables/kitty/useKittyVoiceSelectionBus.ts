/**
 * Voice `select_node` → Pinia selection (Kitty child index aware).
 */
import { onUnmounted } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { resolveKittyChildNodeId } from '@/composables/kitty/kittyDiagramChildren'
import { useDiagramStore } from '@/stores/diagram'

const VOICE_SELECT_OWNER_SUFFIX = '_KittyVoiceSelection'

export function useKittyVoiceSelectionBus(ownerId: string): void {
  const diagramStore = useDiagramStore()
  const listenerOwner = `${ownerId}${VOICE_SELECT_OWNER_SUFFIX}`

  eventBus.onWithOwner(
    'selection:select_requested',
    (data) => {
      const nodes = diagramStore.data?.nodes ?? []
      const nodeId = resolveKittyChildNodeId(diagramStore.type, nodes, {
        nodeId: data.nodeId,
        nodeIndex: data.nodeIndex,
      })
      if (nodeId) {
        diagramStore.selectNodes([nodeId])
      }
    },
    listenerOwner
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(listenerOwner)
  })
}
