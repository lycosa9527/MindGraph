/**
 * Mobile detection composable using @vueuse/core breakpoints.
 * Returns a reactive `isMobile` flag (true when viewport < 768px or touch UA).
 * Office / word-addin embeds always count as desktop.
 */
import { computed, ref } from 'vue'

import { useBreakpoints } from '@vueuse/core'

import { isTouchDeviceUserAgent } from '@/utils/isMobileClient'
import {
  isOfficeEmbedDesktop,
  syncOfficeEmbedFromSearch,
} from '@/utils/officeEmbed'

const breakpoints = useBreakpoints({ mobile: 768 })
const isSmallViewport = breakpoints.smaller('mobile')

const isTouchDevice = computed(() => isTouchDeviceUserAgent())

const embedEpoch = ref(0)

/** Sync Office/word-addin embed flag from route query; call from the router. */
export function refreshOfficeEmbedLayout(
  query?: Record<string, unknown> | string
): string {
  const client = syncOfficeEmbedFromSearch(query)
  embedEpoch.value += 1
  return client
}

export function useMobileDetect() {
  const isMobile = computed(() => {
    void embedEpoch.value
    if (isOfficeEmbedDesktop()) {
      return false
    }
    return isSmallViewport.value || isTouchDevice.value
  })

  return { isMobile, isSmallViewport, isTouchDevice }
}
