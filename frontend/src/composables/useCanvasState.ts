/**
 * useCanvasState - VueFlow + VueUse Canvas Integration
 *
 * Provides reactive canvas state management combining:
 * - VueUse's useElementSize for reactive container dimensions
 * - VueUse's useMediaQuery for responsive breakpoints
 * - VueUse's useDebounceFn for optimized resize handling
 * - VueFlow's fitView for auto-fitting diagrams
 *
 * Usage:
 *   const containerRef = ref<HTMLElement | null>(null)
 *   const { width, height, isMobile, debouncedFit } = useCanvasState(containerRef)
 */
import { computed, watch, type Ref } from 'vue'

import { useVueFlow } from '@vue-flow/core'
import { useDebounceFn, useElementSize, useMediaQuery } from '@vueuse/core'

import { ANIMATION, BREAKPOINTS, FIT_PADDING } from '@/config/uiConfig'

// ============================================================================
// Types
// ============================================================================

export interface UseCanvasStateOptions {
  /** Debounce delay for resize handling (ms) */
  resizeDebounce?: number
  /** Padding for fitView operations */
  fitPadding?: number
  /** Animation duration for fitView */
  fitDuration?: number
  /** Minimum size change to trigger re-fit (px) */
  minSizeChangeThreshold?: number
  /** Auto-fit when container size changes */
  autoFitOnResize?: boolean
}

export interface CanvasState {
  /** Container width in pixels */
  width: Ref<number>
  /** Container height in pixels */
  height: Ref<number>
  /** Is mobile viewport (< 768px) */
  isMobile: Ref<boolean>
  /** Is tablet viewport (< 1024px) */
  isTablet: Ref<boolean>
  /** Is desktop viewport (>= 1024px) */
  isDesktop: Ref<boolean>
  /** Debounced fit function */
  debouncedFit: () => void
  /** Immediate fit function */
  fitNow: (animate?: boolean) => void
}

// ============================================================================
// Composable
// ============================================================================

export function useCanvasState(
  containerRef: Ref<HTMLElement | null>,
  options: UseCanvasStateOptions = {}
): CanvasState {
  const {
    resizeDebounce = ANIMATION.RESIZE_DEBOUNCE,
    fitPadding = FIT_PADDING.STANDARD,
    fitDuration = ANIMATION.DURATION_NORMAL,
    minSizeChangeThreshold = 50,
    autoFitOnResize = true,
  } = options

  // =========================================================================
  // VueUse: Reactive Container Dimensions
  // =========================================================================

  const { width, height } = useElementSize(containerRef)

  // =========================================================================
  // VueUse: Responsive Breakpoints
  // =========================================================================

  const isMobile = useMediaQuery(`(max-width: ${BREAKPOINTS.MOBILE}px)`)
  const isTablet = useMediaQuery(`(max-width: ${BREAKPOINTS.TABLET}px)`)
  const isDesktop = computed(() => !isTablet.value)

  // =========================================================================
  // VueFlow: Fit View Integration
  // =========================================================================

  const { fitView, getNodes } = useVueFlow()

  /**
   * Fit diagram to canvas with animation
   */
  function fitNow(animate = true): void {
    if (getNodes.value.length === 0) return

    fitView({
      padding: fitPadding,
      duration: animate ? fitDuration : 0,
    })
  }

  /**
   * Debounced fit for resize events
   */
  const debouncedFit = useDebounceFn(() => {
    fitNow(true)
  }, resizeDebounce)

  // =========================================================================
  // Auto-fit on Resize
  // =========================================================================

  if (autoFitOnResize) {
    watch(
      [width, height],
      ([newW, newH], [oldW, oldH]) => {
        // Only refit if:
        // 1. Old dimensions were valid (not initial 0 -> value)
        // 2. Size change exceeds threshold
        const widthChanged = Math.abs(newW - oldW) > minSizeChangeThreshold
        const heightChanged = Math.abs(newH - oldH) > minSizeChangeThreshold

        if (oldW > 0 && oldH > 0 && (widthChanged || heightChanged)) {
          debouncedFit()
        }
      },
      { flush: 'post' }
    )
  }

  // =========================================================================
  // Return
  // =========================================================================

  return {
    width,
    height,
    isMobile,
    isTablet,
    isDesktop,
    debouncedFit,
    fitNow,
  }
}
