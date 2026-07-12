/**
 * Desktop canvas Kitty owner — holds WS for verified mutation apply/ack (S10–S13).
 * Mobile is mic+chat only; this agent owns diagram_update apply for the open canvas.
 */
import { type ComputedRef, type Ref, onUnmounted, watch } from 'vue'

import { buildKittyDiagramContext } from '@/composables/kitty/buildKittyDiagramContext'
import { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import { useDiagramStore } from '@/stores/diagram'
import { useOneSentenceStore } from '@/stores/oneSentence'
import { useKittySessionStore } from '@/stores/kittySession'

export function useKittyCanvasOwnerAgent(options: {
  libraryDiagramId: Ref<string | null> | ComputedRef<string | null>
  enabled: ComputedRef<boolean>
}): {
  kitty: ReturnType<typeof useKittyAgent>
  ensureConnected: () => Promise<boolean>
} {
  const diagramStore = useDiagramStore()
  const oneSentence = useOneSentenceStore()
  const kittySession = useKittySessionStore()

  const kitty = useKittyAgent({
    ownerId: 'KittyCanvasOwner',
    textOnly: true,
    onError: () => {
      /* canvas owner is silent — chat surfaces own errors */
    },
  })

  function buildContext() {
    return buildKittyDiagramContext(diagramStore, 'one_sentence', {
      oneSentencePhase: oneSentence.phase,
    })
  }

  kitty.registerDiagramContextBuilder(buildContext)

  async function ensureConnected(): Promise<boolean> {
    if (!options.enabled.value) {
      return false
    }
    const scope = options.libraryDiagramId.value?.trim() ?? ''
    if (!scope) {
      return false
    }
    if (kitty.isConnected.value && kitty.isLiveForScope(scope)) {
      kittySession.setOwnsKittySession(true)
      return true
    }
    try {
      await kitty.startConversation(scope, buildContext())
      kittySession.setOwnsKittySession(true)
      return kitty.isConnected.value
    } catch {
      return false
    }
  }

  watch(
    [options.enabled, options.libraryDiagramId],
    () => {
      if (!options.enabled.value) {
        return
      }
      void ensureConnected()
    },
    { immediate: true }
  )

  onUnmounted(() => {
    kittySession.setOwnsKittySession(false)
    void kitty.stopConversation()
  })

  return { kitty, ensureConnected }
}
