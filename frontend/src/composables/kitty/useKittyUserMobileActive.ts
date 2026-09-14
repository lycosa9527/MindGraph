/**
 * ``mobile_active`` for desktop canvas: SSE hub is SoT; one REST GET if the hub
 * is empty when the canvas starts listening.
 */
import { type Ref, computed, onUnmounted, ref, watch } from 'vue'

import {
  isKittyMobileActiveHubFresh,
  publishKittyMobileActiveHub,
  useKittyMobileActiveHubSnapshot,
} from '@/composables/kitty/kittyDesktopMobileActiveHub'
import { apiRequest } from '@/utils/apiClient'

interface MobileActivePayload {
  active?: unknown
  scopes?: unknown
  primary_scope?: unknown
}

export function useKittyUserMobileActive(listenEnabled: Ref<boolean>) {
  const hubSnapshot = useKittyMobileActiveHubSnapshot()
  const active = ref(false)
  const scopes = ref<string[]>([])
  const primaryScope = ref<string | null>(null)
  let hydrateInFlight = false

  function applyHubToRefs(): void {
    const hub = hubSnapshot.value
    active.value = hub.active
    scopes.value = [...hub.scopes]
    primaryScope.value = hub.primaryScope
  }

  function clearRefs(): void {
    active.value = false
    scopes.value = []
    primaryScope.value = null
  }

  async function hydrate(): Promise<void> {
    if (!listenEnabled.value) {
      clearRefs()
      return
    }
    if (isKittyMobileActiveHubFresh()) {
      applyHubToRefs()
      return
    }
    if (hydrateInFlight) {
      return
    }
    hydrateInFlight = true
    try {
      const res = await apiRequest('/api/kitty/mobile_active', { method: 'GET' })
      if (!listenEnabled.value) {
        return
      }
      if (isKittyMobileActiveHubFresh()) {
        applyHubToRefs()
        return
      }
      if (!res.ok) {
        clearRefs()
        return
      }
      const data = (await res.json()) as MobileActivePayload
      if (isKittyMobileActiveHubFresh()) {
        applyHubToRefs()
        return
      }
      publishKittyMobileActiveHub(data)
      applyHubToRefs()
    } catch {
      clearRefs()
    } finally {
      hydrateInFlight = false
    }
  }

  function syncListen(): void {
    if (!listenEnabled.value) {
      clearRefs()
      return
    }
    applyHubToRefs()
    if (!isKittyMobileActiveHubFresh()) {
      void hydrate()
    }
  }

  watch(listenEnabled, syncListen, { immediate: true })

  watch(
    hubSnapshot,
    () => {
      if (!listenEnabled.value) {
        return
      }
      applyHubToRefs()
    },
    { deep: true }
  )

  onUnmounted(() => {
    clearRefs()
  })

  const hubFresh = computed(() => isKittyMobileActiveHubFresh())

  return { active, scopes, primaryScope, refresh: hydrate, hubFresh }
}
