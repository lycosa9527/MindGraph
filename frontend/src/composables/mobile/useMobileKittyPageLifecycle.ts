/**
 * Mobile Kitty page mount/teardown and WS disconnect notice.
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

export interface UseMobileKittyPageLifecycleOptions {
  router: Router
  authStore: ReturnType<typeof useAuthStore>
  featureFlagsStore: ReturnType<typeof useFeatureFlagsStore>
  kitty: ReturnType<typeof useKittyAgent>
  kittyPairScope: Ref<string>
  bootstrapPayload: Ref<MobileKittyBootstrapPayload | null | undefined>
  ensureMobileKittyBootstrap: () => Promise<void>
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
    bindKittyMicKeyboard,
    teardownMicPtt,
    pushKittyDebugLine,
    translate,
    notifyWarning,
  } = options

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
    eventBus.onWithOwner(
      'voice:ws_closed',
      (data) => {
        if (data.wasClean) {
          return
        }
        notifyWarning(
          translate(
            'mobile.kittyDisconnected',
            'Voice connection lost. Hold the mic to reconnect.'
          )
        )
      },
      'MobileKittyPage_WsClosed'
    )
  })

  onUnmounted(async () => {
    eventBus.removeAllListenersForOwner('MobileKittyPage_WsClosed')
    teardownMicPtt()
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
