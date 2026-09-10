/**
 * Measure the bottom edge of canvas chrome so overlays (collab rail, learning-sheet
 * bars) sit below the title row, ribbon tools, and the live session banner.
 */
import { onMounted, onUnmounted, ref } from 'vue'

/** Prefer the session banner (it sits under the toolbar) then the chrome header. */
const CHROME_SELECTORS = [
  '[data-collab-session-banner]',
  '.canvas-chrome',
  '.canvas-top-bar--mindmap',
  '.canvas-top-bar',
] as const

/** Classic single-row top bar (~48px) plus a small gap — used before layout. */
export const CANVAS_CHROME_BOTTOM_FALLBACK_PX = 56

export function measureCanvasChromeBottomPx(): number {
  for (const selector of CHROME_SELECTORS) {
    const el = document.querySelector(selector)
    if (!(el instanceof HTMLElement)) {
      continue
    }
    const rect = el.getBoundingClientRect()
    if (rect.height > 0) {
      return Math.round(rect.bottom)
    }
  }
  return CANVAS_CHROME_BOTTOM_FALLBACK_PX
}

export function useCanvasChromeBottomOffset(gapPx = 8) {
  const offsetPx = ref(CANVAS_CHROME_BOTTOM_FALLBACK_PX + gapPx)
  let observer: ResizeObserver | null = null

  function update(): void {
    offsetPx.value = measureCanvasChromeBottomPx() + gapPx
  }

  function bindObserver(): void {
    observer?.disconnect()
    if (typeof ResizeObserver === 'undefined') {
      return
    }
    observer = new ResizeObserver(() => {
      update()
    })
    for (const selector of CHROME_SELECTORS) {
      const el = document.querySelector(selector)
      if (el instanceof Element) {
        observer.observe(el)
      }
    }
  }

  onMounted(() => {
    update()
    bindObserver()
    window.addEventListener('resize', update)
  })

  onUnmounted(() => {
    observer?.disconnect()
    observer = null
    window.removeEventListener('resize', update)
  })

  return { offsetPx, update, bindObserver }
}
