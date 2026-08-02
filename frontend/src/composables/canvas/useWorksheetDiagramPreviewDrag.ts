/**
 * Drag / resize worksheet diagram in the A4 preview.
 * Offsets [-1, 1] (0 = centered); scale (0.25–1) relative to max-fit size.
 */
import { computed, onUnmounted, ref, type Ref } from 'vue'

export const WORKSHEET_DIAGRAM_SCALE_MIN = 0.25
export const WORKSHEET_DIAGRAM_SCALE_MAX = 1
/** Normalized offset threshold for center guides + soft snap. */
export const WORKSHEET_DIAGRAM_CENTER_SNAP = 0.08

type InteractionMode = 'move' | 'resize'
type ResizeHandle = 'nw' | 'ne' | 'sw' | 'se'

function maybeSnapToCenter(value: number): number {
  const clamped = clampOffset(value)
  return Math.abs(clamped) <= WORKSHEET_DIAGRAM_CENTER_SNAP ? 0 : clamped
}

function clampOffset(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.max(-1, Math.min(1, value))
}

function clampScale(value: number): number {
  if (!Number.isFinite(value)) return 1
  return Math.max(WORKSHEET_DIAGRAM_SCALE_MIN, Math.min(WORKSHEET_DIAGRAM_SCALE_MAX, value))
}

function maxFitSize(
  img: HTMLImageElement,
  body: HTMLElement
): { width: number; height: number } {
  const boxW = body.clientWidth
  const boxH = body.clientHeight
  const naturalW = img.naturalWidth
  const naturalH = img.naturalHeight
  if (boxW <= 0 || boxH <= 0 || naturalW <= 0 || naturalH <= 0) {
    return { width: 0, height: 0 }
  }
  const fit = Math.min(boxW / naturalW, boxH / naturalH)
  return { width: naturalW * fit, height: naturalH * fit }
}

function isResizeHandle(value: string | undefined): value is ResizeHandle {
  return value === 'nw' || value === 'ne' || value === 'sw' || value === 'se'
}

export function clampWorksheetDiagramOffset(value: unknown, fallback = 0): number {
  if (typeof value !== 'number') return fallback
  return clampOffset(value)
}

export function clampWorksheetDiagramScale(value: unknown, fallback = 1): number {
  if (typeof value !== 'number') return fallback
  return clampScale(value)
}

export function useWorksheetDiagramPreviewDrag(options: {
  offsetX: Ref<number>
  offsetY: Ref<number>
  scale: Ref<number>
  enabled: Ref<boolean>
}) {
  const diagramBodyRef = ref<HTMLElement | null>(null)
  const diagramImgRef = ref<HTMLImageElement | null>(null)
  const diagramFrameRef = ref<HTMLElement | null>(null)
  const dragging = ref(false)
  const resizing = ref(false)

  const baseFitW = ref(0)
  const baseFitH = ref(0)
  const freeXRatio = ref(0)
  const freeYRatio = ref(0)

  let pointerId: number | null = null
  let mode: InteractionMode = 'move'
  let resizeHandle: ResizeHandle = 'se'
  let startClientX = 0
  let startClientY = 0
  let startOffsetX = 0
  let startOffsetY = 0
  let startScale = 1
  let startFrameW = 0
  let startFrameH = 0

  const frameSize = computed(() => {
    const scale = clampScale(options.scale.value)
    return {
      width: baseFitW.value * scale,
      height: baseFitH.value * scale,
    }
  })

  const diagramFrameStyle = computed(() => {
    const x = clampOffset(options.offsetX.value)
    const y = clampOffset(options.offsetY.value)
    const size = frameSize.value
    return {
      width: `${size.width}px`,
      height: `${size.height}px`,
      left: `calc(50% + ${x * freeXRatio.value * 50}%)`,
      top: `calc(50% + ${y * freeYRatio.value * 50}%)`,
    }
  })

  const interacting = computed(() => dragging.value || resizing.value)

  const showCenterGuideX = computed(() => {
    if (!interacting.value || freeXRatio.value <= 0) return false
    return Math.abs(clampOffset(options.offsetX.value)) <= WORKSHEET_DIAGRAM_CENTER_SNAP
  })

  const showCenterGuideY = computed(() => {
    if (!interacting.value || freeYRatio.value <= 0) return false
    return Math.abs(clampOffset(options.offsetY.value)) <= WORKSHEET_DIAGRAM_CENTER_SNAP
  })

  function syncGeometry(): void {
    const body = diagramBodyRef.value
    const img = diagramImgRef.value
    if (!body || !img) {
      baseFitW.value = 0
      baseFitH.value = 0
      freeXRatio.value = 0
      freeYRatio.value = 0
      return
    }
    const fit = maxFitSize(img, body)
    baseFitW.value = fit.width
    baseFitH.value = fit.height
    const scale = clampScale(options.scale.value)
    const frameW = fit.width * scale
    const frameH = fit.height * scale
    const freeW = Math.max(0, body.clientWidth - frameW)
    const freeH = Math.max(0, body.clientHeight - frameH)
    freeXRatio.value = body.clientWidth > 0 ? freeW / body.clientWidth : 0
    freeYRatio.value = body.clientHeight > 0 ? freeH / body.clientHeight : 0
  }

  function onFramePointerDown(event: PointerEvent): void {
    if (!options.enabled.value) return
    const body = diagramBodyRef.value
    const frame = diagramFrameRef.value
    if (!body || !frame || event.button !== 0) return

    syncGeometry()
    const handleAttr = (event.target as HTMLElement | null)?.dataset?.handle
    const handle = isResizeHandle(handleAttr) ? handleAttr : null

    pointerId = event.pointerId
    startClientX = event.clientX
    startClientY = event.clientY
    startOffsetX = clampOffset(options.offsetX.value)
    startOffsetY = clampOffset(options.offsetY.value)
    startScale = clampScale(options.scale.value)
    startFrameW = frameSize.value.width
    startFrameH = frameSize.value.height

    if (handle) {
      mode = 'resize'
      resizeHandle = handle
      resizing.value = true
      dragging.value = false
    } else {
      mode = 'move'
      dragging.value = true
      resizing.value = false
      const freeW = Math.max(0, body.clientWidth - startFrameW)
      const freeH = Math.max(0, body.clientHeight - startFrameH)
      if (freeW < 1 && freeH < 1) {
        dragging.value = false
        pointerId = null
        return
      }
    }

    frame.setPointerCapture(event.pointerId)
    event.preventDefault()
  }

  function onFramePointerMove(event: PointerEvent): void {
    if (pointerId !== event.pointerId) return
    const body = diagramBodyRef.value
    if (!body) return

    const dx = event.clientX - startClientX
    const dy = event.clientY - startClientY

    if (mode === 'move' && dragging.value) {
      const freeW = Math.max(0, body.clientWidth - startFrameW)
      const freeH = Math.max(0, body.clientHeight - startFrameH)
      const nextX = freeW > 0 ? startOffsetX + dx / (freeW / 2) : startOffsetX
      const nextY = freeH > 0 ? startOffsetY + dy / (freeH / 2) : startOffsetY
      options.offsetX.value = freeW > 0 ? maybeSnapToCenter(nextX) : clampOffset(nextX)
      options.offsetY.value = freeH > 0 ? maybeSnapToCenter(nextY) : clampOffset(nextY)
      return
    }

    if (mode === 'resize' && resizing.value && startFrameW > 0 && startFrameH > 0) {
      const signedDx =
        resizeHandle === 'ne' || resizeHandle === 'se' ? dx : -dx
      const signedDy =
        resizeHandle === 'sw' || resizeHandle === 'se' ? dy : -dy
      const factor = 1 + (signedDx / startFrameW + signedDy / startFrameH) / 2
      const nextScale = clampScale(startScale * factor)
      options.scale.value = nextScale

      // Keep placement valid as free space changes with scale.
      const nextFrameW = baseFitW.value * nextScale
      const nextFrameH = baseFitH.value * nextScale
      const freeW = Math.max(0, body.clientWidth - nextFrameW)
      const freeH = Math.max(0, body.clientHeight - nextFrameH)
      freeXRatio.value = body.clientWidth > 0 ? freeW / body.clientWidth : 0
      freeYRatio.value = body.clientHeight > 0 ? freeH / body.clientHeight : 0
      options.offsetX.value = clampOffset(options.offsetX.value)
      options.offsetY.value = clampOffset(options.offsetY.value)
    }
  }

  function endInteraction(event: PointerEvent): void {
    if (pointerId !== event.pointerId) return
    dragging.value = false
    resizing.value = false
    pointerId = null
    const frame = diagramFrameRef.value
    if (frame?.hasPointerCapture(event.pointerId)) {
      frame.releasePointerCapture(event.pointerId)
    }
    syncGeometry()
  }

  function onDiagramImageLoad(): void {
    syncGeometry()
  }

  function resetInteraction(): void {
    dragging.value = false
    resizing.value = false
    pointerId = null
  }

  onUnmounted(() => {
    resetInteraction()
  })

  return {
    diagramBodyRef,
    diagramImgRef,
    diagramFrameRef,
    dragging,
    resizing,
    showCenterGuideX,
    showCenterGuideY,
    diagramFrameStyle,
    onFramePointerDown,
    onFramePointerMove,
    onFramePointerUp: endInteraction,
    onFramePointerCancel: endInteraction,
    onDiagramImageLoad,
    syncFreeSpace: syncGeometry,
    resetInteraction,
  }
}
