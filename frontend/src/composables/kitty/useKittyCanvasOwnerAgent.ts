/**
 * Desktop canvas Kitty owner — holds WS for verified mutation apply/ack (S10–S13).
 * Mobile is mic+chat only; this agent owns diagram_update apply for the open canvas.
 *
 * Also keeps Hub live_spec aligned with Pinia after local replaces (e.g. whole-diagram
 * auto_complete via loadFromSpec) even when the one-sentence panel is closed.
 */
import { type ComputedRef, type Ref, onUnmounted, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { buildKittyDiagramContext } from '@/composables/kitty/buildKittyDiagramContext'
import { getKittyDiagramContentFingerprint } from '@/composables/kitty/kittyDiagramFingerprint'
import { runKittyHubSync } from '@/composables/kitty/pipeline/hubSyncWorker'
import { KITTY_HUB_BACKGROUND_SYNC_TIMEOUT_MS } from '@/composables/kitty/syncKittyHubContext'
import { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import { useDiagramStore } from '@/stores/diagram'
import { useOneSentenceStore } from '@/stores/oneSentence'
import { useKittySessionStore } from '@/stores/kittySession'

const RECONNECT_DEBOUNCE_MS = 400
const HUB_BACKGROUND_DEBOUNCE_MS = 500

export function useKittyCanvasOwnerAgent(options: {
  /** Kitty scope SoT: library id when saved, else shared ephemeral / open_canvas scope. */
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

  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let hubSyncTimer: ReturnType<typeof setTimeout> | null = null
  let lastHubFingerprint = ''

  function buildContext() {
    return buildKittyDiagramContext(diagramStore, 'one_sentence', {
      oneSentencePhase: oneSentence.phase,
    })
  }

  kitty.registerDiagramContextBuilder(buildContext)

  function clearReconnectTimer(): void {
    if (reconnectTimer != null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function clearHubSyncTimer(): void {
    if (hubSyncTimer != null) {
      clearTimeout(hubSyncTimer)
      hubSyncTimer = null
    }
  }

  function scheduleReconnect(): void {
    if (!options.enabled.value) {
      return
    }
    clearReconnectTimer()
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      void ensureConnected()
    }, RECONNECT_DEBOUNCE_MS)
  }

  function releaseOwnership(): void {
    clearReconnectTimer()
    clearHubSyncTimer()
    lastHubFingerprint = ''
    kittySession.setOwnsKittySession(false)
    kittySession.setMutationAckSender(null)
    void kitty.stopConversation()
  }

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
      const live = kitty.isConnected.value && kitty.isLiveForScope(scope)
      kittySession.setOwnsKittySession(live)
      if (live) {
        lastHubFingerprint = getKittyDiagramContentFingerprint(diagramStore.data)
      }
      return live
    } catch {
      kittySession.setOwnsKittySession(false)
      return false
    }
  }

  function scheduleBackgroundHubSync(): void {
    if (!options.enabled.value || !kittySession.ownsKittySession || !kitty.isConnected.value) {
      return
    }
    clearHubSyncTimer()
    hubSyncTimer = setTimeout(() => {
      hubSyncTimer = null
      if (!options.enabled.value || !kittySession.ownsKittySession || !kitty.isConnected.value) {
        return
      }
      const fingerprint = getKittyDiagramContentFingerprint(diagramStore.data)
      if (!fingerprint || fingerprint === lastHubFingerprint) {
        return
      }
      const scope = options.libraryDiagramId.value?.trim() ?? ''
      void runKittyHubSync({
        deps: {
          buildContext,
          updateContext: kitty.updateContext,
          getScope: () => options.libraryDiagramId.value,
          isConnected: () => kitty.isConnected.value,
          lane: 'desktop',
        },
        ctx: {
          requestId: `owner-bg-${Date.now()}`,
          scope: scope || 'scope',
          lane: 'desktop',
        },
        reason: 'background',
        timeoutMs: KITTY_HUB_BACKGROUND_SYNC_TIMEOUT_MS,
      }).then((result) => {
        if (result.ok) {
          lastHubFingerprint = fingerprint
        }
      })
    }, HUB_BACKGROUND_DEBOUNCE_MS)
  }

  watch(
    [options.enabled, options.libraryDiagramId],
    () => {
      if (!options.enabled.value) {
        releaseOwnership()
        return
      }
      const scope = options.libraryDiagramId.value?.trim() ?? ''
      if (!scope) {
        releaseOwnership()
        return
      }
      void ensureConnected()
    },
    { immediate: true }
  )

  watch(
    () => getKittyDiagramContentFingerprint(diagramStore.data),
    () => {
      scheduleBackgroundHubSync()
    }
  )

  eventBus.onWithOwner(
    'voice:ws_closed',
    () => {
      if (!options.enabled.value) {
        return
      }
      scheduleReconnect()
    },
    'KittyCanvasOwnerAgent'
  )

  function onVisibilityChange(): void {
    if (typeof document === 'undefined') {
      return
    }
    if (document.visibilityState !== 'visible') {
      return
    }
    if (!options.enabled.value) {
      return
    }
    scheduleReconnect()
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibilityChange)
  }

  onUnmounted(() => {
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
    eventBus.removeAllListenersForOwner('KittyCanvasOwnerAgent')
    releaseOwnership()
  })

  return { kitty, ensureConnected }
}
