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
  isKittyWsIntentionalClose,
  isKittyWsPolicyDenyClose,
} from '@/composables/kitty/kittyConnectFailure'
import {
  type KittyConnectAttemptResult,
  classifyKittyConnectError,
  createKittyWsAuthReconnectGate,
  runKittyConnectWithAuthRecovery,
} from '@/composables/kitty/kittyWsAuthReconnect'
import { getKittyDiagramContentFingerprint } from '@/composables/kitty/kittyDiagramFingerprint'
import { runKittyHubSync } from '@/composables/kitty/pipeline/hubSyncWorker'
import { KITTY_HUB_BACKGROUND_SYNC_TIMEOUT_MS } from '@/composables/kitty/syncKittyHubContext'
import { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import { lectureSpeakGeneration } from '@/composables/mindMap/useMindClassroomLecture'
import { useAuthStore } from '@/stores/auth'
import { useDiagramStore } from '@/stores/diagram'
import { useOneSentenceStore } from '@/stores/oneSentence'
import { useKittySessionStore } from '@/stores/kittySession'

const RECONNECT_DEBOUNCE_MS = 400
const RECONNECT_MAX_BACKOFF_MS = 8_000
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
  /** Exponential backoff after failed ensureConnected (reset on success / scope change). */
  let reconnectAttempt = 0
  /** Bumped on scope/enabled changes so stale ensureConnected results are ignored. */
  let connectGeneration = 0

  function buildContext() {
    return buildKittyDiagramContext(diagramStore, 'one_sentence', {
      oneSentencePhase: oneSentence.phase,
    })
  }

  kitty.registerDiagramContextBuilder(buildContext)

  function clearReconnectTimer(): void {
    if (reconnectTimer != null) {
      clearTimeout(reconnectTimer)
    }
    reconnectTimer = null
  }

  function clearHubSyncTimer(): void {
    if (hubSyncTimer != null) {
      clearTimeout(hubSyncTimer)
      hubSyncTimer = null
    }
  }

  function reconnectDelayMs(): number {
    return Math.min(
      RECONNECT_MAX_BACKOFF_MS,
      RECONNECT_DEBOUNCE_MS * 2 ** Math.min(reconnectAttempt, 5)
    )
  }

  function scheduleReconnect(): void {
    if (!options.enabled.value || authGate.isHardStopped() || releasingOwnership) {
      return
    }
    if (ensureInFlight != null) {
      return
    }
    clearReconnectTimer()
    const delay = reconnectDelayMs()
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      void ensureConnected()
    }, delay)
  }

  async function releaseOwnership(): Promise<void> {
    releasingOwnership = true
    connectGeneration += 1
    clearReconnectTimer()
    clearHubSyncTimer()
    lastHubFingerprint = ''
    kittySession.setOwnsKittySession(false)
    kittySession.setMutationAckSender(null)
    try {
      await kitty.stopConversation()
    } finally {
      releasingOwnership = false
    }
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
      return classifyKittyConnectError(error)
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
    const generation = connectGeneration
    ensureInFlight = (async () => {
      try {
        const ok = await runKittyConnectWithAuthRecovery({
          isHardStopped: authGate.isHardStopped,
          markHardStopped: authGate.markHardStopped,
          hasAuthenticatedUser: () => Boolean(authStore.isAuthenticated || authStore.user),
          canAttemptAuthRefresh: authGate.canAttemptAuthRefresh,
          markAuthRefreshConsumed: authGate.markAuthRefreshConsumed,
          onSessionExpired: () => {
            authStore.handleTokenExpired(
              'Your session has expired. Please log in again.',
              undefined,
              { skipRecovery: true }
            )
          },
          connectOnce,
        })
        if (generation !== connectGeneration) {
          return false
        }
        if (ok) {
          reconnectAttempt = 0
        } else if (!authGate.isHardStopped()) {
          reconnectAttempt += 1
        }
        return ok
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
        reconnectAttempt = 0
      }
      if (!options.enabled.value) {
        void releaseOwnership()
        return
      }
      const scope = options.libraryDiagramId.value?.trim() ?? ''
      if (!scope) {
        void releaseOwnership()
        return
      }
      const scopeChanged = previous != null && previous[1] !== current[1]
      if (scopeChanged) {
        authGate.reset()
        reconnectAttempt = 0
        connectGeneration += 1
        // Serialize: stop prior socket before opening the new scope so cleanup
        // / preempt races cannot leave a short-lived accepted peer thrashing.
        void (async () => {
          const generation = connectGeneration
          releasingOwnership = true
          clearReconnectTimer()
          try {
            await kitty.stopConversation()
          } finally {
            releasingOwnership = false
          }
          if (generation !== connectGeneration) {
            return
          }
          if (!options.enabled.value) {
            return
          }
          const nextScope = options.libraryDiagramId.value?.trim() ?? ''
          if (!nextScope) {
            return
          }
          scheduleReconnect()
        })()
        return
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
        reconnectAttempt = 0
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
    'kitty:lecture_narrate_requested',
    (payload) => {
      void (async () => {
        const requestedGeneration = payload.generation
        const connected = await ensureConnected()
        if (
          requestedGeneration !== undefined &&
          requestedGeneration !== lectureSpeakGeneration()
        ) {
          return
        }
        const prefetch =
          payload.prefetchText?.trim()
            ? { text: payload.prefetchText, stepId: payload.prefetchStepId }
            : undefined
        if (!connected || !kitty.sendNarrate(payload.text, payload.stepId, prefetch)) {
          eventBus.emit('kitty:lecture_tts_done', { fallback: true })
        }
      })()
    },
    'KittyCanvasOwnerAgent'
  )

  eventBus.onWithOwner(
    'kitty:lecture_interrupt_requested',
    () => {
      kitty.stopAudioPlayback()
      const socket = kitty.ws.value
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'tts_interrupt' }))
      }
    },
    'KittyCanvasOwnerAgent'
  )

  eventBus.onWithOwner(
    'voice:ws_closed',
    (payload?: {
      wasClean?: boolean
      code?: number
      reason?: string
      scope?: string
    }) => {
      if (!options.enabled.value || authGate.isHardStopped() || releasingOwnership) {
        return
      }
      const currentScope = options.libraryDiagramId.value?.trim() ?? ''
      if (!currentScope) {
        return
      }
      // Ignore closes for a different scope (stale handoff / cleanup of prior id).
      if (payload?.scope && payload.scope !== currentScope) {
        return
      }
      // Intentional server/client closes (preempt, cleanup, local reconnect).
      if (isKittyWsIntentionalClose(payload?.code, payload?.wasClean)) {
        return
      }
      // Policy denials — do not reconnect-storm.
      if (isKittyWsPolicyDenyClose(payload?.code)) {
        authGate.markHardStopped()
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
    void releaseOwnership()
  })

  return { kitty, ensureConnected }
}
