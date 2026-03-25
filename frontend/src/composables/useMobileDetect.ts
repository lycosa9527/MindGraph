/**
 * Mobile detection composable using @vueuse/core breakpoints.
 * Returns a reactive `isMobile` flag (true when viewport < 768px).
 * Also checks navigator.userAgent for touch-only devices that may
 * report a desktop-class viewport (e.g. iPad with keyboard).
 */
import { computed } from 'vue'

import { useBreakpoints } from '@vueuse/core'

const breakpoints = useBreakpoints({ mobile: 768 })
const isSmallViewport = breakpoints.smaller('mobile')

const isTouchDevice = computed(() => {
  if (typeof navigator === 'undefined') return false
  return /Android|iPhone|iPad|iPod|webOS|BlackBerry|IEMobile|Opera Mini/i.test(
    navigator.userAgent,
  )
})

export function useMobileDetect() {
  const isMobile = computed(() => isSmallViewport.value || isTouchDevice.value)

  return { isMobile, isSmallViewport, isTouchDevice }
}
