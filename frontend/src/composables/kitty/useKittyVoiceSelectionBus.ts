/**
 * Voice `select_node` → Pinia selection (Kitty child index aware).
 */
import { onUnmounted } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { applyKittySelectionTarget } from '@/composables/kitty/kittySelectionApply'

const VOICE_SELECT_OWNER_SUFFIX = '_KittyVoiceSelection'

export function useKittyVoiceSelectionBus(
  ownerId: string,
  options?: { onSelectionApplied?: () => void }
): void {
  const listenerOwner = `${ownerId}${VOICE_SELECT_OWNER_SUFFIX}`

  eventBus.onWithOwner(
    'selection:select_requested',
    (data) => {
      const applied = applyKittySelectionTarget(
        { nodeId: data.nodeId, nodeIndex: data.nodeIndex },
        { canvasHighlight: false }
      )
      if (applied) {
        options?.onSelectionApplied?.()
      }
    },
    listenerOwner
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(listenerOwner)
  })
}
