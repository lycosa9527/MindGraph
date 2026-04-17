/**
 * IP-based registration UI mode (mainland China vs international vs both).
 * Reads mg_client_region cookie first; otherwise GET /api/auth/client-region.
 */
import { type Ref, computed, ref, watch } from 'vue'

import {
  type ClientRegion,
  readClientRegionCookie,
  readUnknownRegionSessionFallback,
  setUnknownRegionSessionFallback,
} from '@/utils/clientRegion'

export function useRegisterRegionDetection(
  modalVisible: Ref<boolean>,
  currentView: Ref<'login' | 'register' | 'sms-login' | 'forgot-password'>
) {
  const registerRegion = ref<ClientRegion | null>(null)
  const registerRegionLoading = ref(false)
  let clientRegionFetch: Promise<void> | null = null

  const isBothRegister = computed(() => registerRegion.value === 'both')

  function applyRegisterRegion(region: ClientRegion) {
    registerRegion.value = region
  }

  async function ensureRegisterRegion() {
    const cached = readClientRegionCookie()
    if (cached) {
      applyRegisterRegion(cached)
      return
    }
    if (readUnknownRegionSessionFallback()) {
      applyRegisterRegion('both')
      return
    }
    if (clientRegionFetch) {
      return clientRegionFetch
    }
    registerRegionLoading.value = true
    clientRegionFetch = (async () => {
      try {
        const response = await fetch('/api/auth/client-region', { credentials: 'same-origin' })
        const data = (await response.json().catch(() => ({}))) as {
          mainland_china?: boolean | null
        }
        if (data.mainland_china === true) {
          applyRegisterRegion('cn')
        } else if (data.mainland_china === false) {
          applyRegisterRegion('intl')
        } else {
          applyRegisterRegion('both')
          setUnknownRegionSessionFallback()
        }
      } catch {
        applyRegisterRegion('both')
        setUnknownRegionSessionFallback()
      } finally {
        registerRegionLoading.value = false
        clientRegionFetch = null
      }
    })()
    return clientRegionFetch
  }

  watch(
    () => [modalVisible.value, currentView.value] as const,
    ([visible, view]) => {
      if (visible && view === 'register') {
        void ensureRegisterRegion()
      }
    },
    { immediate: true }
  )

  return {
    registerRegion,
    registerRegionLoading,
    isBothRegister,
  }
}
