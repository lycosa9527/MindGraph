export interface ViewportState {
  x: number
  y: number
  zoom: number
}

/** Smooth step easing for presentation camera moves. */
export function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2
}

let activeTransitionCancel: (() => void) | null = null

export function cancelViewportTransition(): void {
  activeTransitionCancel?.()
  activeTransitionCancel = null
}

/**
 * Interpolate viewport with requestAnimationFrame (cinema-style camera).
 * Returns a promise that resolves when the animation completes or is cancelled.
 */
export function animateViewportTransition(
  from: ViewportState,
  to: ViewportState,
  durationMs: number,
  onFrame: (viewport: ViewportState) => void
): Promise<void> {
  cancelViewportTransition()

  return new Promise((resolve) => {
    const start = performance.now()
    let cancelled = false

    activeTransitionCancel = () => {
      cancelled = true
      activeTransitionCancel = null
      resolve()
    }

    function tick(now: number): void {
      if (cancelled) return
      const raw = durationMs <= 0 ? 1 : Math.min(1, (now - start) / durationMs)
      const t = easeInOutCubic(raw)
      onFrame({
        x: from.x + (to.x - from.x) * t,
        y: from.y + (to.y - from.y) * t,
        zoom: from.zoom + (to.zoom - from.zoom) * t,
      })
      if (raw < 1) {
        requestAnimationFrame(tick)
      } else {
        activeTransitionCancel = null
        resolve()
      }
    }

    requestAnimationFrame(tick)
  })
}
