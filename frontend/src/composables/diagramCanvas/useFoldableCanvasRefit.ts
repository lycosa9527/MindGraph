/**
 * Refit when the canvas box changes width, and the first time it leaves a
 * 0×0 box. A fold changes the window; the page hears that as a resize, and
 * Vue Flow does not fit itself. A keyboard only changes height, so that
 * resize is ignored.
 */
import { type Ref, onMounted, onUnmounted } from 'vue'

import { isTouchDeviceUserAgent } from '@/utils/isMobileClient'

const WIDTH_DELTA_PX = 80
const FOLD_SETTLE_MS = 250

export function foldCanvasNeedsRefit(
  previousWidth: number,
  previousHeight: number,
  nextWidth: number,
  nextHeight: number,
  touchClient: boolean
): boolean {
  if (nextWidth < 2 || nextHeight < 2) return false
  if (previousWidth < 2 || previousHeight < 2) return true
  if (!touchClient) return false
  return Math.abs(nextWidth - previousWidth) >= WIDTH_DELTA_PX
}

export function useFoldableCanvasRefit(container: Ref<HTMLElement | null>, fit: () => void): void {
  let lastWidth = 0
  let lastHeight = 0
  let timer: ReturnType<typeof setTimeout> | null = null
  let observer: ResizeObserver | null = null

  function readBox(): { width: number; height: number } | null {
    const el = container.value
    if (!el) return null
    if (el.clientWidth < 2 || el.clientHeight < 2) return null
    return { width: el.clientWidth, height: el.clientHeight }
  }

  function apply(): void {
    timer = null
    const box = readBox()
    if (!box) return
    const refit = foldCanvasNeedsRefit(
      lastWidth,
      lastHeight,
      box.width,
      box.height,
      isTouchDeviceUserAgent()
    )
    lastWidth = box.width
    lastHeight = box.height
    if (!refit) return
    fit()
  }

  function schedule(): void {
    const box = readBox()
    const recovering = lastWidth < 2 || lastHeight < 2
    if (!box) return
    if (!recovering && box.width === lastWidth && box.height === lastHeight) return
    if (timer != null) clearTimeout(timer)
    if (recovering) {
      apply()
      return
    }
    timer = setTimeout(apply, FOLD_SETTLE_MS)
  }

  onMounted(() => {
    const el = container.value
    if (!el || typeof ResizeObserver === 'undefined') return
    const box = readBox()
    if (box) {
      lastWidth = box.width
      lastHeight = box.height
    }
    observer = new ResizeObserver(schedule)
    observer.observe(el)
  })

  onUnmounted(() => {
    if (timer != null) clearTimeout(timer)
    observer?.disconnect()
    observer = null
  })
}
