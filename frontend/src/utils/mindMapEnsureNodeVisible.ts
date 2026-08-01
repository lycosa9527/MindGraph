/**
 * Pan-only "keep node in view" math for mind-map child add.
 * Keeps current zoom; shifts x/y so the node lies in the central safeFraction
 * of the usable canvas (default 0.75 → ~12.5% inset each side).
 */

export type ViewportXYZoom = {
  x: number
  y: number
  zoom: number
}

export type FlowRect = {
  x: number
  y: number
  width: number
  height: number
}

export type ScreenInsets = {
  top: number
  right: number
  bottom: number
  left: number
}

export type EnsureNodeVisibleInput = {
  viewport: ViewportXYZoom
  node: FlowRect
  viewWidth: number
  viewHeight: number
  /** Fraction of usable canvas that counts as the safe zone (0–1). */
  safeFraction?: number
  chromeInsets?: Partial<ScreenInsets>
}

export type EnsureNodeVisibleResult = {
  changed: boolean
  viewport: ViewportXYZoom
}

function clampFraction(value: number): number {
  if (!Number.isFinite(value)) return 0.75
  return Math.min(1, Math.max(0.2, value))
}

/**
 * Compute a pan-only viewport that keeps `node` inside the central safe area.
 * Returns the input viewport unchanged when already inside (or zoom invalid).
 */
export function computePanToKeepNodeInSafeFraction(
  input: EnsureNodeVisibleInput
): EnsureNodeVisibleResult {
  const zoom = input.viewport.zoom
  if (!(zoom > 0) || input.viewWidth <= 0 || input.viewHeight <= 0) {
    return { changed: false, viewport: { ...input.viewport } }
  }

  const safeFraction = clampFraction(input.safeFraction ?? 0.75)
  const chrome: ScreenInsets = {
    top: input.chromeInsets?.top ?? 0,
    right: input.chromeInsets?.right ?? 0,
    bottom: input.chromeInsets?.bottom ?? 0,
    left: input.chromeInsets?.left ?? 0,
  }

  const usableLeft = chrome.left
  const usableTop = chrome.top
  const usableRight = input.viewWidth - chrome.right
  const usableBottom = input.viewHeight - chrome.bottom
  const usableW = usableRight - usableLeft
  const usableH = usableBottom - usableTop
  if (usableW <= 0 || usableH <= 0) {
    return { changed: false, viewport: { ...input.viewport } }
  }

  const insetX = (usableW * (1 - safeFraction)) / 2
  const insetY = (usableH * (1 - safeFraction)) / 2
  const safeLeft = usableLeft + insetX
  const safeRight = usableRight - insetX
  const safeTop = usableTop + insetY
  const safeBottom = usableBottom - insetY

  const nodeW = Math.max(0, input.node.width) * zoom
  const nodeH = Math.max(0, input.node.height) * zoom
  let screenLeft = input.node.x * zoom + input.viewport.x
  let screenTop = input.node.y * zoom + input.viewport.y
  let screenRight = screenLeft + nodeW
  let screenBottom = screenTop + nodeH

  let dx = 0
  let dy = 0

  if (nodeW >= safeRight - safeLeft) {
    const centerX = (safeLeft + safeRight) / 2
    dx = centerX - (screenLeft + nodeW / 2)
  } else {
    if (screenLeft < safeLeft) dx = safeLeft - screenLeft
    else if (screenRight > safeRight) dx = safeRight - screenRight
  }

  if (nodeH >= safeBottom - safeTop) {
    const centerY = (safeTop + safeBottom) / 2
    dy = centerY - (screenTop + nodeH / 2)
  } else {
    if (screenTop < safeTop) dy = safeTop - screenTop
    else if (screenBottom > safeBottom) dy = safeBottom - screenBottom
  }

  if (dx === 0 && dy === 0) {
    return { changed: false, viewport: { ...input.viewport } }
  }

  return {
    changed: true,
    viewport: {
      x: input.viewport.x + dx,
      y: input.viewport.y + dy,
      zoom,
    },
  }
}
