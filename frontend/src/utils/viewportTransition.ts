export interface ViewportState {
  x: number
  y: number
  zoom: number
}

/** Smooth step easing for presentation camera moves. */
export function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2
}

/** Editor fits stay on this lane. The library demo uses its own so the two cameras do not cancel each other. */
export const EDITOR_VIEWPORT_LANE = 'editor'

const laneCancel = new Map<string, () => void>()

function laneKey(lane?: string): string {
  return lane || EDITOR_VIEWPORT_LANE
}

export function cancelViewportTransition(lane?: string): void {
  const key = laneKey(lane)
  const cancel = laneCancel.get(key)
  if (!cancel) return
  laneCancel.delete(key)
  cancel()
}

/**
 * Interpolate viewport with requestAnimationFrame (cinema-style camera).
 * Returns a promise that resolves when the animation completes or is cancelled.
 */
export function animateViewportTransition(
  from: ViewportState,
  to: ViewportState,
  durationMs: number,
  onFrame: (viewport: ViewportState) => void,
  lane?: string
): Promise<void> {
  const key = laneKey(lane)
  cancelViewportTransition(key)

  return new Promise((resolve) => {
    const start = performance.now()
    let cancelled = false

    const cancel = (): void => {
      cancelled = true
      if (laneCancel.get(key) === cancel) laneCancel.delete(key)
      resolve()
    }
    laneCancel.set(key, cancel)

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
        if (laneCancel.get(key) === cancel) laneCancel.delete(key)
        resolve()
      }
    }

    requestAnimationFrame(tick)
  })
}
