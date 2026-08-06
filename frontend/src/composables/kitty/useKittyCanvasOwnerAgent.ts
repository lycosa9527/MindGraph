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
import {
  type KittyConnectAttemptResult,
  createKittyWsAuthReconnectGate,
  isKittyConnectAbortError,
  runKittyConnectWithAuthRecovery,
} from '@/composables/kitty/kittyWsAuthReconnect'
import { getKittyDiagramContentFingerprint } from '@/composables/kitty/kittyDiagramFingerprint'
import { runKittyHubSync } from '@/composables/kitty/pipeline/hubSyncWorker'
import { KITTY_HUB_BACKGROUND_SYNC_TIMEOUT_MS } from '@/composables/kitty/syncKittyHubContext'
import { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import { useAuthStore } from '@/stores/auth'
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
  const authStore = useAuthStore()
  const diagramStore = useDiagramStore()
  const oneSentence = useOneSentenceStore()
  const kittySession = useKittySessionStore()
  const authGate = createKittyWsAuthReconnectGate()

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
  let ensureInFlight: Promise<boolean> | null = null
  /** True while intentionally tearing down — ignore voice:ws_closed reconnect. */
  let releasingOwnership = false

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
    if (!options.enabled.value || authGate.isHardStopped() || releasingOwnership) {
      return
    }
    if (ensureInFlight != null) {
      return
    }
    clearReconnectTimer()
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      void ensureConnected()
    }, RECONNECT_DEBOUNCE_MS)
  }

  function releaseOwnership(): void {
    releasingOwnership = true
    clearReconnectTimer()
    clearHubSyncTimer()
    lastHubFingerprint = ''
    kittySession.setOwnsKittySession(false)
    kittySession.setMutationAckSender(null)
    void kitty.stopConversation().finally(() => {
      releasingOwnership = false
    })
  }

  async function connectOnce(): Promise<KittyConnectAttemptResult> {
    if (!options.enabled.value || releasingOwnership) {
      return 'aborted'
    }
    const scope = options.libraryDiagramId.value?.trim() ?? ''
    if (!scope) {
      return 'aborted'
    }
    if (kitty.isConnected.value && kitty.isLiveForScope(scope)) {
      kittySession.setOwnsKittySession(true)
      return 'connected'
    }
    try {
      await kitty.startConversation(scope, buildContext())
      const live = kitty.isConnected.value && kitty.isLiveForScope(scope)
      kittySession.setOwnsKittySession(live)
      if (live) {
        lastHubFingerprint = getKittyDiagramContentFingerprint(diagramStore.data)
        return 'connected'
      }
      return 'failed'
    } catch (error) {
      kittySession.setOwnsKittySession(false)
      if (isKittyConnectAbortError(error)) {
        return 'aborted'
      }
      return 'failed'
    }
  }

  async function ensureConnected(): Promise<boolean> {
    if (!options.enabled.value || authGate.isHardStopped() || releasingOwnership) {
      return false
    }
    const scope = options.libraryDiagramId.value?.trim() ?? ''
    if (!scope) {
      return false
    }
    if (ensureInFlight != null) {
      return ensureInFlight
    }
    ensureInFlight = (async () => {
      try {
        return await runKittyConnectWithAuthRecovery({
          isHardStopped: authGate.isHardStopped,
          markHardStopped: authGate.markHardStopped,
          hasAuthenticatedUser: () => Boolean(authStore.isAuthenticated || authStore.user),
          onSessionExpired: () => {
            authStore.handleTokenExpired(
              'Your session has expired. Please log in again.',
              undefined
            )
          },
          connectOnce,
        })
      } finally {
        ensureInFlight = null
      }
    })()
    return ensureInFlight
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
      const hubScope = options.libraryDiagramId.value?.trim() ?? ''
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
          scope: hubScope || 'scope',
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
    (current, previous) => {
      const enabled = current[0]
      const wasEnabled = previous?.[0]
      if (enabled && wasEnabled === false) {
        authGate.reset()
      }
      if (!options.enabled.value) {
        releaseOwnership()
        return
      }
      const scope = options.libraryDiagramId.value?.trim() ?? ''
      if (!scope) {
        releaseOwnership()
        return
      }
      // Scope change: allow one auth refresh again for the new socket.
      if (previous != null && previous[1] !== current[1]) {
        authGate.reset()
      }
      // Debounce so loadFromSpec first paint is not competing with WS start +
      // full diagram context JSON.stringify on the main thread.
      scheduleReconnect()
    },
    { immediate: true }
  )

  watch(
    () => authStore.isAuthenticated,
    (authenticated, wasAuthenticated) => {
      if (authenticated && !wasAuthenticated) {
        authGate.reset()
      }
      if (!authenticated) {
        authGate.markHardStopped()
        clearReconnectTimer()
      }
    }
  )

  watch(
    () => getKittyDiagramContentFingerprint(diagramStore.data),
    () => {
      scheduleBackgroundHubSync()
    }
  )

  eventBus.onWithOwner(
    'voice:ws_closed',
    (payload?: { wasClean?: boolean }) => {
      if (!options.enabled.value || authGate.isHardStopped() || releasingOwnership) {
        return
      }
      // Intentional close during ownership handoff — do not fight stopConversation.
      if (payload?.wasClean === true) {
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
    if (!options.enabled.value || authGate.isHardStopped() || releasingOwnership) {
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
