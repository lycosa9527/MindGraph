import { nextTick, onUnmounted, ref, watch, type Ref } from 'vue'

const BUBBLE_GAP_PX = 14
const VIEW_PAD_PX = 8
/** Fallback before the teleported bubble has been measured. */
const ESTIMATED_BUBBLE_WIDTH_PX = 260
const ESTIMATED_BUBBLE_HEIGHT_PX = 110

export type ExplainBubblePlacement = 'right' | 'left' | 'above' | 'below'

export type ExplainBubblePosition = {
  left: number
  top: number
  visible: boolean
  placement: ExplainBubblePlacement
}

export type ExplainBubbleSize = {
  width: number
  height: number
}

type RectBox = {
  left: number
  top: number
  right: number
  bottom: number
}

function hiddenPosition(): ExplainBubblePosition {
  return { left: 0, top: 0, visible: false, placement: 'right' }
}

function spaceOnSides(node: RectBox, container: RectBox): Record<ExplainBubblePlacement, number> {
  return {
    right: container.right - node.right,
    left: node.left - container.left,
    above: node.top - container.top,
    below: container.bottom - node.bottom,
  }
}

function neededSpace(
  placement: ExplainBubblePlacement,
  width: number,
  height: number,
  gap: number,
  pad: number
): number {
  if (placement === 'left' || placement === 'right') {
    return width + gap + pad
  }
  return height + gap + pad
}

function pickPlacement(
  node: RectBox,
  container: RectBox,
  width: number,
  height: number,
  gap: number,
  pad: number
): ExplainBubblePlacement {
  const space = spaceOnSides(node, container)
  const nodeCenterX = (node.left + node.right) / 2
  const canvasCenterX = (container.left + container.right) / 2
  const preferRight = nodeCenterX <= canvasCenterX
  const horizontal: ExplainBubblePlacement[] = preferRight ? ['right', 'left'] : ['left', 'right']
  const vertical: ExplainBubblePlacement[] =
    space.below >= space.above ? ['below', 'above'] : ['above', 'below']

  for (const placement of [...horizontal, ...vertical]) {
    if (space[placement] >= neededSpace(placement, width, height, gap, pad)) {
      return placement
    }
  }

  const ranked = (Object.keys(space) as ExplainBubblePlacement[]).sort(
    (a, b) => space[b] - space[a]
  )
  return ranked[0] ?? 'right'
}

function clamp(value: number, min: number, max: number): number {
  if (min > max) return (min + max) / 2
  return Math.min(Math.max(value, min), max)
}

/**
 * Anchor a short gloss bubble beside a node, flipping around it to stay on canvas.
 */
export function resolveNodeExplainBubbleAnchor(options: {
  nodeBounds: RectBox
  containerBounds: RectBox
  bubbleWidth?: number
  bubbleHeight?: number
  gapPx?: number
  padPx?: number
}): ExplainBubblePosition {
  const gap = options.gapPx ?? BUBBLE_GAP_PX
  const pad = options.padPx ?? VIEW_PAD_PX
  const width = options.bubbleWidth ?? ESTIMATED_BUBBLE_WIDTH_PX
  const height = options.bubbleHeight ?? ESTIMATED_BUBBLE_HEIGHT_PX
  const { nodeBounds, containerBounds } = options

  const placement = pickPlacement(nodeBounds, containerBounds, width, height, gap, pad)
  const nodeCenterX = (nodeBounds.left + nodeBounds.right) / 2
  const nodeCenterY = (nodeBounds.top + nodeBounds.bottom) / 2

  let left = nodeCenterX
  let top = nodeCenterY

  if (placement === 'right') {
    left = nodeBounds.right + gap
    top = nodeCenterY
  } else if (placement === 'left') {
    left = nodeBounds.left - gap
    top = nodeCenterY
  } else if (placement === 'above') {
    left = nodeCenterX
    top = nodeBounds.top - gap
  } else {
    left = nodeCenterX
    top = nodeBounds.bottom + gap
  }

  const minLeft = containerBounds.left + pad
  const maxLeft = containerBounds.right - pad
  const minTop = containerBounds.top + pad
  const maxTop = containerBounds.bottom - pad

  if (placement === 'right') {
    left = clamp(left, minLeft, maxLeft - width)
    top = clamp(top, minTop + height / 2, maxTop - height / 2)
  } else if (placement === 'left') {
    left = clamp(left, minLeft + width, maxLeft)
    top = clamp(top, minTop + height / 2, maxTop - height / 2)
  } else if (placement === 'above') {
    left = clamp(left, minLeft + width / 2, maxLeft - width / 2)
    top = clamp(top, minTop + height, maxTop)
  } else {
    left = clamp(left, minLeft + width / 2, maxLeft - width / 2)
    top = clamp(top, minTop, maxTop - height)
  }

  return { left, top, visible: true, placement }
}

export function useNodeExplainBubblePosition(options: {
  containerRef: Ref<HTMLElement | null>
  nodeId: Ref<string | null>
  enabled: Ref<boolean>
  bubbleSize?: Ref<ExplainBubbleSize | null>
}) {
  const position = ref<ExplainBubblePosition>(hiddenPosition())

  let rafId = 0

  function hide() {
    cancelAnimationFrame(rafId)
    rafId = 0
    position.value = hiddenPosition()
  }

  function measure() {
    const nodeId = options.nodeId.value
    const container = options.containerRef.value
    if (!options.enabled.value || !nodeId || !container) {
      hide()
      return
    }

    const nodeEl = container.querySelector(`.vue-flow__node[data-id="${nodeId}"]`)
    if (!nodeEl) {
      hide()
      return
    }

    const nodeRect = nodeEl.getBoundingClientRect()
    const containerBounds = container.getBoundingClientRect()
    const measured = options.bubbleSize?.value
    position.value = resolveNodeExplainBubbleAnchor({
      nodeBounds: {
        left: nodeRect.left,
        top: nodeRect.top,
        right: nodeRect.right,
        bottom: nodeRect.bottom,
      },
      containerBounds: {
        left: containerBounds.left,
        top: containerBounds.top,
        right: containerBounds.right,
        bottom: containerBounds.bottom,
      },
      bubbleWidth: measured && measured.width > 0 ? measured.width : undefined,
      bubbleHeight: measured && measured.height > 0 ? measured.height : undefined,
    })
  }

  function scheduleMeasure() {
    if (!options.enabled.value || !options.nodeId.value) {
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
        options.nodeId.value ?? '',
        options.enabled.value,
        options.bubbleSize?.value?.width ?? 0,
        options.bubbleSize?.value?.height ?? 0,
      ] as const,
    scheduleMeasure,
    { immediate: true }
  )

  window.addEventListener('resize', scheduleMeasure)
  window.addEventListener('scroll', scheduleMeasure, true)

  onUnmounted(() => {
    cancelAnimationFrame(rafId)
    window.removeEventListener('resize', scheduleMeasure)
    window.removeEventListener('scroll', scheduleMeasure, true)
  })

  return {
    position,
    scheduleMeasure,
  }
}
