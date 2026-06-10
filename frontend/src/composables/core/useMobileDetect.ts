/**
 * Mobile detection composable using @vueuse/core breakpoints.
 * Returns a reactive `isMobile` flag (true when viewport < 768px or touch UA).
 */
import { computed } from 'vue'

import { useBreakpoints } from '@vueuse/core'

import { isTouchDeviceUserAgent } from '@/utils/isMobileClient'

const breakpoints = useBreakpoints({ mobile: 768 })
const isSmallViewport = breakpoints.smaller('mobile')

const isTouchDevice = computed(() => isTouchDeviceUserAgent())

export function useMobileDetect() {
  const isMobile = computed(() => isSmallViewport.value || isTouchDevice.value)

  return { isMobile, isSmallViewport, isTouchDevice }
}
