/**
 * ``mobile_active`` for desktop canvas: prefers cross-tab SSE hub; REST poll only when stale.
 */
import { type Ref, computed, onUnmounted, ref, watch } from 'vue'

import {
  isKittyMobileActiveHubFresh,
  publishKittyMobileActiveHub,
  useKittyMobileActiveHubSnapshot,
} from '@/composables/kitty/kittyDesktopMobileActiveHub'
import { KITTY_MOBILE_WATCH_MS } from '@/composables/kitty/runKittyIntervalPoll'

interface MobileActivePayload {
  active?: unknown
  scopes?: unknown
  primary_scope?: unknown
}

export function useKittyUserMobileActive(pollEnabled: Ref<boolean>) {
  const hubSnapshot = useKittyMobileActiveHubSnapshot()
  const active = ref(false)
  const scopes = ref<string[]>([])
  const primaryScope = ref<string | null>(null)
  let intervalId: ReturnType<typeof setInterval> | null = null
  let tickInFlight = false

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

  async function tick(): Promise<void> {
    if (!pollEnabled.value) {
      clearRefs()
      return
    }
    if (isKittyMobileActiveHubFresh()) {
      applyHubToRefs()
      return
    }
    if (tickInFlight) {
      return
    }
    tickInFlight = true
    try {
      const res = await fetch('/api/kitty/mobile_active', { credentials: 'same-origin' })
      if (!pollEnabled.value) {
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
      tickInFlight = false
    }
  }

  function stopPolling(): void {
    if (intervalId != null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  function syncPolling(): void {
    stopPolling()
    if (!pollEnabled.value) {
      clearRefs()
      return
    }
    applyHubToRefs()
    if (isKittyMobileActiveHubFresh()) {
      return
    }
    void tick()
    intervalId = setInterval(() => {
      if (isKittyMobileActiveHubFresh()) {
        applyHubToRefs()
        stopPolling()
        return
      }
      void tick()
    }, KITTY_MOBILE_WATCH_MS)
  }

  watch(pollEnabled, syncPolling, { immediate: true })

  watch(
    hubSnapshot,
    () => {
      if (!pollEnabled.value) {
        return
      }
      applyHubToRefs()
      if (isKittyMobileActiveHubFresh()) {
        stopPolling()
      }
    },
    { deep: true }
  )

  onUnmounted(() => {
    stopPolling()
    clearRefs()
  })

  const hubFresh = computed(() => isKittyMobileActiveHubFresh())

  return { active, scopes, primaryScope, refresh: tick, hubFresh }
}
