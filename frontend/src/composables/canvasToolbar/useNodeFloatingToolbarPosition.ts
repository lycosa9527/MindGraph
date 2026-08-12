import { nextTick, onUnmounted, ref, watch, type Ref } from 'vue'

const TOOLBAR_GAP_PX = 10
const VIEW_PAD_PX = 8
/** Fallback before the teleported bar has been measured. */
const ESTIMATED_TOOLBAR_HEIGHT_PX = 40
const ESTIMATED_TOOLBAR_WIDTH_PX = 360

export type FloatingToolbarPlacement = 'above' | 'below'

export type FloatingToolbarPosition = {
  left: number
  top: number
  visible: boolean
  placement: FloatingToolbarPlacement
}

export type FloatingToolbarSize = {
  width: number
  height: number
}

type RectBox = {
  left: number
  top: number
  right: number
  bottom: number
}

function hiddenPosition(): FloatingToolbarPosition {
  return { left: 0, top: 0, visible: false, placement: 'above' }
}

/**
 * Anchor the floating toolbar so it stays inside the canvas container.
 * Prefer above the selection; flip below when fit-to-screen leaves no room on top.
 */
export function resolveFloatingToolbarAnchor(options: {
  nodeBounds: RectBox
  containerBounds: RectBox
  toolbarHeight?: number
  toolbarWidth?: number
  gapPx?: number
  padPx?: number
}): FloatingToolbarPosition {
  const gap = options.gapPx ?? TOOLBAR_GAP_PX
  const pad = options.padPx ?? VIEW_PAD_PX
  const height = options.toolbarHeight ?? ESTIMATED_TOOLBAR_HEIGHT_PX
  const width = options.toolbarWidth ?? ESTIMATED_TOOLBAR_WIDTH_PX
  const { nodeBounds, containerBounds } = options

  const centerX = (nodeBounds.left + nodeBounds.right) / 2
  const aboveAnchorY = nodeBounds.top - gap
  const belowAnchorY = nodeBounds.bottom + gap

  const fitsAbove = aboveAnchorY - height >= containerBounds.top + pad
  const fitsBelow = belowAnchorY + height <= containerBounds.bottom - pad

  let placement: FloatingToolbarPlacement = 'above'
  let top = aboveAnchorY

  if (!fitsAbove && fitsBelow) {
    placement = 'below'
    top = belowAnchorY
  } else if (!fitsAbove && !fitsBelow) {
    const spaceAbove = aboveAnchorY - (containerBounds.top + pad)
    const spaceBelow = containerBounds.bottom - pad - belowAnchorY
    if (spaceBelow > spaceAbove) {
      placement = 'below'
      top = Math.min(belowAnchorY, containerBounds.bottom - pad - height)
      top = Math.max(top, containerBounds.top + pad)
    } else {
      placement = 'above'
      top = Math.max(aboveAnchorY, containerBounds.top + pad + height)
      top = Math.min(top, containerBounds.bottom - pad)
    }
  }

  const halfWidth = width / 2
  const minCenterX = containerBounds.left + pad + halfWidth
  const maxCenterX = containerBounds.right - pad - halfWidth
  let left = centerX
  if (minCenterX <= maxCenterX) {
    left = Math.min(Math.max(centerX, minCenterX), maxCenterX)
  } else {
    left = (containerBounds.left + containerBounds.right) / 2
  }

  return { left, top, visible: true, placement }
}

export function useNodeFloatingToolbarPosition(options: {
  containerRef: Ref<HTMLElement | null>
  selectedNodeIds: Ref<string[]>
  /** When false, toolbar hides immediately (no rAF delay). */
  enabled: Ref<boolean>
  /** Measured bar size from the mounted toolbar (preferred over estimates). */
  toolbarSize?: Ref<FloatingToolbarSize | null>
}) {
  const position = ref<FloatingToolbarPosition>(hiddenPosition())

  let rafId = 0

  function hide() {
    cancelAnimationFrame(rafId)
    rafId = 0
    position.value = hiddenPosition()
  }

  function measure() {
    const ids = options.selectedNodeIds.value
    const container = options.containerRef.value
    if (!options.enabled.value || ids.length === 0 || !container) {
      hide()
      return
    }

    let minLeft = Infinity
    let minTop = Infinity
    let maxRight = -Infinity
    let maxBottom = -Infinity
    let found = 0

    for (const nodeId of ids) {
      const nodeEl = container.querySelector(`.vue-flow__node[data-id="${nodeId}"]`)
      if (!nodeEl) continue
      const nodeRect = nodeEl.getBoundingClientRect()
      minLeft = Math.min(minLeft, nodeRect.left)
      minTop = Math.min(minTop, nodeRect.top)
      maxRight = Math.max(maxRight, nodeRect.right)
      maxBottom = Math.max(maxBottom, nodeRect.bottom)
      found += 1
    }

    if (found === 0) {
      hide()
      return
    }

    const measured = options.toolbarSize?.value
    const containerBounds = container.getBoundingClientRect()
    position.value = resolveFloatingToolbarAnchor({
      nodeBounds: {
        left: minLeft,
        top: minTop,
        right: maxRight,
        bottom: maxBottom,
      },
      containerBounds: {
        left: containerBounds.left,
        top: containerBounds.top,
        right: containerBounds.right,
        bottom: containerBounds.bottom,
      },
      toolbarWidth: measured && measured.width > 0 ? measured.width : undefined,
      toolbarHeight: measured && measured.height > 0 ? measured.height : undefined,
    })
  }

  function scheduleMeasure() {
    // Suppressors (e.g. open modal) must clear the teleported toolbar in the same tick.
    if (!options.enabled.value || options.selectedNodeIds.value.length === 0) {
      hide()
      return
    }
    cancelAnimationFrame(rafId)
    rafId = requestAnimationFrame(() => {
      void nextTick(measure)
    })
  }

  watch(
    () =>
      [
        options.selectedNodeIds.value.join('|'),
        options.enabled.value,
        options.toolbarSize?.value?.width ?? 0,
        options.toolbarSize?.value?.height ?? 0,
      ] as const,
    scheduleMeasure,
    { immediate: true }
  )

  onUnmounted(() => {
    cancelAnimationFrame(rafId)
  })

  return {
    position,
    scheduleMeasure,
  }
}
