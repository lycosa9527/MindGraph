/**
 * Mobile Kitty page mount/teardown, WS reconnect, and Pinia pipeline cleanup.
 */
import { onMounted, onUnmounted, type Ref } from 'vue'
import type { Router } from 'vue-router'

import { eventBus } from '@/composables/core/useEventBus'
import { hydrateMobileKittyFromLibrary } from '@/composables/kitty/hydrateMobileKittyFromLibrary'
import { hydrateMobileKittyStoreFromBootstrap } from '@/composables/kitty/hydrateMobileKittyStoreFromBootstrap'
import type { useAuthStore } from '@/stores/auth'
import type { useFeatureFlagsStore } from '@/stores/featureFlags'
import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import type { MobileKittyBootstrapPayload } from '@/composables/kitty/useMobileKittyPairing'
import { useKittyPipelineStore } from '@/stores/kittyPipeline'
import { useKittySessionStore } from '@/stores/kittySession'

const RECONNECT_DEBOUNCE_MS = 400

export interface UseMobileKittyPageLifecycleOptions {
  router: Router
  authStore: ReturnType<typeof useAuthStore>
  featureFlagsStore: ReturnType<typeof useFeatureFlagsStore>
  kitty: ReturnType<typeof useKittyAgent>
  kittyPairScope: Ref<string>
  bootstrapPayload: Ref<MobileKittyBootstrapPayload | null | undefined>
  ensureMobileKittyBootstrap: () => Promise<void>
  /** Pre-open Kitty WS so first PTT hold is not racing connect. */
  ensureConnected?: () => Promise<boolean>
  kittyServerEnabled?: { value: boolean }
  bindKittyMicKeyboard: () => void
  teardownMicPtt: () => void
  pushKittyDebugLine: (prefix: string, detail: string) => void
  translate: (key: string, fallback?: string) => string
  notifyWarning: (message: string) => void
}

export function useMobileKittyPageLifecycle(options: UseMobileKittyPageLifecycleOptions): void {
  const {
    router,
    authStore,
    featureFlagsStore,
    kitty,
    kittyPairScope,
    bootstrapPayload,
    ensureMobileKittyBootstrap,
    ensureConnected,
    kittyServerEnabled,
    bindKittyMicKeyboard,
    teardownMicPtt,
    pushKittyDebugLine,
    translate,
    notifyWarning,
  } = options

  const pipelineStore = useKittyPipelineStore()
  const kittySession = useKittySessionStore()
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let disposed = false

  function clearReconnectTimer(): void {
    if (reconnectTimer != null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function scheduleReconnect(): void {
    if (disposed || !ensureConnected || kittyServerEnabled?.value === false) {
      return
    }
    clearReconnectTimer()
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (disposed) {
        return
      }
      void ensureConnected()
    }, RECONNECT_DEBOUNCE_MS)
  }

  function resetLocalKittyUiState(): void {
    pipelineStore.resetToIdle()
    pipelineStore.clearTraces()
    kittySession.setAsrListening(false)
    kittySession.setAsrPartialTranscript('')
  }

  onMounted(async () => {
    await featureFlagsStore.fetchFlags()
    if (!authStore.isAuthenticated) {
      router.replace('/m')
      return
    }
    pushKittyDebugLine('#', 'debug log ready')
    bindKittyMicKeyboard()
    await ensureMobileKittyBootstrap()
    const boot = bootstrapPayload.value
    if (boot && boot.source !== 'empty') {
      const libRaw =
        boot.context?.diagram_library_id ??
        (boot.source === 'library' ? boot.recommended_scope : null)
      const libId = typeof libRaw === 'string' ? libRaw.trim() : ''
      if (boot.source === 'library' && libId) {
        await hydrateMobileKittyFromLibrary(libId)
      } else if (boot.context) {
        hydrateMobileKittyStoreFromBootstrap(boot.context, boot.diagram_type ?? 'circle_map')
      }
    }
    if (kittyServerEnabled?.value && ensureConnected) {
      void ensureConnected()
    }
    eventBus.onWithOwner(
      'voice:ws_closed',
      (data) => {
        if (data.wasClean) {
          return
        }
        // Drop mid-turn pipeline so unclean reconnect cannot stick awaiting_result.
        resetLocalKittyUiState()
        notifyWarning(
          translate(
            'mobile.kittyDisconnected',
            'Voice connection lost. Reconnecting…'
          )
        )
        scheduleReconnect()
      },
      'MobileKittyPage_WsClosed'
    )
  })

  function onVisibilityChange(): void {
    if (typeof document === 'undefined') {
      return
    }
    if (document.visibilityState !== 'visible') {
      return
    }
    scheduleReconnect()
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibilityChange)
  }

  onUnmounted(async () => {
    disposed = true
    clearReconnectTimer()
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
    eventBus.removeAllListenersForOwner('MobileKittyPage_WsClosed')
    teardownMicPtt()
    resetLocalKittyUiState()
    await kitty.stopConversation()
    if (authStore.isAuthenticated && featureFlagsStore.getFeatureKittyAgent()) {
      fetch(`/api/kitty/cleanup/${encodeURIComponent(kittyPairScope.value)}`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
      }).catch(() => {})
    }
  })
}
