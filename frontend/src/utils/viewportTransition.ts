export interface ViewportState {
  x: number
  y: number
  zoom: number
}

/** Smooth step easing for presentation camera moves. */
export function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2
}

export interface ViewportFrame {
  width: number
  height: number
  /** Screen point the subject should glide toward. Defaults to the canvas center. */
  focusX?: number
  focusY?: number
}

/** One camera sample. Zoom eases while the subject stays on a straight screen path. */
export function viewportFrameAt(
  from: ViewportState,
  to: ViewportState,
  t: number,
  frame?: ViewportFrame
): ViewportState {
  const clamped = Math.min(1, Math.max(0, t))
  const zoom = from.zoom + (to.zoom - from.zoom) * clamped
  if (!frame || frame.width <= 0 || frame.height <= 0 || from.zoom <= 0 || to.zoom <= 0) {
    return {
      x: from.x + (to.x - from.x) * clamped,
      y: from.y + (to.y - from.y) * clamped,
      zoom,
    }
  }
  const focusX = frame.focusX ?? frame.width / 2
  const focusY = frame.focusY ?? frame.height / 2
  const worldX = (focusX - to.x) / to.zoom
  const worldY = (focusY - to.y) / to.zoom
  const screenX = worldX * from.zoom + from.x + (focusX - (worldX * from.zoom + from.x)) * clamped
  const screenY = worldY * from.zoom + from.y + (focusY - (worldY * from.zoom + from.y)) * clamped
  return {
    zoom,
    x: screenX - worldX * zoom,
    y: screenY - worldY * zoom,
  }
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
  lane?: string,
  frame?: ViewportFrame
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
      onFrame(viewportFrameAt(from, to, easeInOutCubic(raw), frame))
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
