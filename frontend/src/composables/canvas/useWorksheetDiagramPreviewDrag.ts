/**
 * Drag, resize, and crop the worksheet diagram in the A4 preview.
 * Offsets [-1, 1] (0 = centered); scale (0.25–1) relative to max-fit size.
 * Crop fractions hide each edge of the source image; the opposite edge stays put.
 */
import { type Ref, computed, onUnmounted, ref } from 'vue'

import {
  type WorksheetDiagramCrop,
  type WorksheetDiagramCropEdge,
  cropEdgeFromDelta,
  normalizeWorksheetDiagramCrop,
  offsetForAnchoredEdge,
  worksheetDiagramCropFractions,
  worksheetDiagramCropKeyDelta,
  worksheetDiagramFrameOrigin,
} from '@/utils/worksheetDiagramCrop'

const WORKSHEET_DIAGRAM_SCALE_MIN = 0.25
const WORKSHEET_DIAGRAM_SCALE_MAX = 1
const CROP_NUDGE = 0.02
/** Normalized offset threshold for center guides + soft snap. */
const WORKSHEET_DIAGRAM_CENTER_SNAP = 0.08

export const DIAGRAM_CROP_EDGES = [
  { id: 'n', edge: 'top', field: 'diagramCropTop', labelKey: 'canvas.worksheetText.cropTop' },
  { id: 'e', edge: 'right', field: 'diagramCropRight', labelKey: 'canvas.worksheetText.cropRight' },
  {
    id: 's',
    edge: 'bottom',
    field: 'diagramCropBottom',
    labelKey: 'canvas.worksheetText.cropBottom',
  },
  { id: 'w', edge: 'left', field: 'diagramCropLeft', labelKey: 'canvas.worksheetText.cropLeft' },
] as const

export type WorksheetDiagramAlign = 'left' | 'center' | 'right'

type InteractionMode = 'move' | 'resize' | 'crop'
type ResizeHandle = 'nw' | 'ne' | 'sw' | 'se'
type CropHandle = (typeof DIAGRAM_CROP_EDGES)[number]['id']

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

function maxFitSize(img: HTMLImageElement, body: HTMLElement): { width: number; height: number } {
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

function isCropHandle(value: string | undefined): value is CropHandle {
  return DIAGRAM_CROP_EDGES.some((item) => item.id === value)
}

function cropEdgeForHandle(handle: CropHandle): WorksheetDiagramCropEdge {
  for (const item of DIAGRAM_CROP_EDGES) {
    if (item.id === handle) return item.edge
  }
  return DIAGRAM_CROP_EDGES[0].edge
}

export function useWorksheetDiagramPreviewDrag(options: {
  offsetX: Ref<number>
  offsetY: Ref<number>
  scale: Ref<number>
  cropTop: Ref<number>
  cropRight: Ref<number>
  cropBottom: Ref<number>
  cropLeft: Ref<number>
  enabled: Ref<boolean>
}) {
  const diagramBodyRef = ref<HTMLElement | null>(null)
  const diagramImgRef = ref<HTMLImageElement | null>(null)
  const diagramFrameRef = ref<HTMLElement | null>(null)
  const dragging = ref(false)
  const resizing = ref(false)
  const croppingAxis = ref<'x' | 'y' | null>(null)

  const baseFitW = ref(0)
  const baseFitH = ref(0)
  const freeXRatio = ref(0)
  const freeYRatio = ref(0)

  let pointerId: number | null = null
  let mode: InteractionMode = 'move'
  let resizeHandle: ResizeHandle = 'se'
  let cropHandle: CropHandle = 'n'
  let startClientX = 0
  let startClientY = 0
  let startOffsetX = 0
  let startOffsetY = 0
  let startScale = 1
  let startFrameW = 0
  let startFrameH = 0
  let startCrop: WorksheetDiagramCrop = { top: 0, right: 0, bottom: 0, left: 0 }
  let anchorLeft = 0
  let anchorTop = 0
  let anchorRight = 0
  let anchorBottom = 0

  function currentCrop(): WorksheetDiagramCrop {
    return normalizeWorksheetDiagramCrop({
      top: options.cropTop.value,
      right: options.cropRight.value,
      bottom: options.cropBottom.value,
      left: options.cropLeft.value,
    })
  }

  function writeCrop(crop: WorksheetDiagramCrop): void {
    const normalized = normalizeWorksheetDiagramCrop(crop)
    options.cropTop.value = normalized.top
    options.cropRight.value = normalized.right
    options.cropBottom.value = normalized.bottom
    options.cropLeft.value = normalized.left
  }

  function scaledFrame(fitW: number, fitH: number): { width: number; height: number } {
    const scale = clampScale(options.scale.value)
    const { cw, ch } = worksheetDiagramCropFractions(currentCrop())
    return { width: fitW * scale * cw, height: fitH * scale * ch }
  }

  const frameSize = computed(() => scaledFrame(baseFitW.value, baseFitH.value))

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

  const diagramImageStyle = computed(() => {
    const crop = currentCrop()
    const { cw, ch } = worksheetDiagramCropFractions(crop)
    return {
      width: `${100 / cw}%`,
      height: `${100 / ch}%`,
      left: `${(-crop.left / cw) * 100}%`,
      top: `${(-crop.top / ch) * 100}%`,
    }
  })

  const interacting = computed(
    () => dragging.value || resizing.value || croppingAxis.value !== null
  )

  function offsetNear(value: number, target: number): boolean {
    return Math.abs(clampOffset(value) - target) < 0.001
  }

  const diagramAlign = computed((): WorksheetDiagramAlign | null => {
    if (offsetNear(options.offsetX.value, -1)) return 'left'
    if (offsetNear(options.offsetX.value, 1)) return 'right'
    if (offsetNear(options.offsetX.value, 0) && offsetNear(options.offsetY.value, 0)) {
      return 'center'
    }
    return null
  })

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
    const frame = scaledFrame(fit.width, fit.height)
    const freeW = Math.max(0, body.clientWidth - frame.width)
    const freeH = Math.max(0, body.clientHeight - frame.height)
    freeXRatio.value = body.clientWidth > 0 ? freeW / body.clientWidth : 0
    freeYRatio.value = body.clientHeight > 0 ? freeH / body.clientHeight : 0
  }

  function alignDiagram(align: WorksheetDiagramAlign): void {
    if (align === 'left') {
      options.offsetX.value = -1
    } else if (align === 'right') {
      options.offsetX.value = 1
    } else {
      options.offsetX.value = 0
      options.offsetY.value = 0
    }
    syncGeometry()
  }

  function onFramePointerDown(event: PointerEvent): void {
    if (!options.enabled.value) return
    const body = diagramBodyRef.value
    const frame = diagramFrameRef.value
    if (!body || !frame || event.button !== 0) return

    syncGeometry()
    const handleAttr = (event.target as HTMLElement | null)?.dataset?.handle
    const resize = isResizeHandle(handleAttr) ? handleAttr : null
    const crop = isCropHandle(handleAttr) ? handleAttr : null

    pointerId = event.pointerId
    startClientX = event.clientX
    startClientY = event.clientY
    startOffsetX = clampOffset(options.offsetX.value)
    startOffsetY = clampOffset(options.offsetY.value)
    startScale = clampScale(options.scale.value)
    startFrameW = frameSize.value.width
    startFrameH = frameSize.value.height
    startCrop = currentCrop()

    if (resize) {
      mode = 'resize'
      resizeHandle = resize
      resizing.value = true
      dragging.value = false
      croppingAxis.value = null
    } else if (crop) {
      mode = 'crop'
      cropHandle = crop
      croppingAxis.value = crop === 'n' || crop === 's' ? 'y' : 'x'
      dragging.value = false
      resizing.value = false
      const origin = worksheetDiagramFrameOrigin(
        body.clientWidth,
        body.clientHeight,
        startFrameW,
        startFrameH,
        startOffsetX,
        startOffsetY
      )
      anchorLeft = origin.left
      anchorTop = origin.top
      anchorRight = origin.right
      anchorBottom = origin.bottom
    } else {
      mode = 'move'
      dragging.value = true
      resizing.value = false
      croppingAxis.value = null
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

  function placeAnchoredCrop(
    edge: WorksheetDiagramCropEdge,
    nextCrop: WorksheetDiagramCrop,
    body: HTMLElement,
    fullW: number,
    fullH: number,
    fixedLeft: number,
    fixedTop: number,
    fixedRight: number,
    fixedBottom: number
  ): void {
    writeCrop(nextCrop)
    const { cw, ch } = worksheetDiagramCropFractions(nextCrop)
    const visW = fullW * cw
    const visH = fullH * ch
    if (edge === 'top') {
      options.offsetY.value = offsetForAnchoredEdge({
        bodySize: body.clientHeight,
        visibleSize: visH,
        fixedEdge: fixedBottom,
        anchor: 'end',
      })
    } else if (edge === 'bottom') {
      options.offsetY.value = offsetForAnchoredEdge({
        bodySize: body.clientHeight,
        visibleSize: visH,
        fixedEdge: fixedTop,
        anchor: 'start',
      })
    } else if (edge === 'left') {
      options.offsetX.value = offsetForAnchoredEdge({
        bodySize: body.clientWidth,
        visibleSize: visW,
        fixedEdge: fixedRight,
        anchor: 'end',
      })
    } else {
      options.offsetX.value = offsetForAnchoredEdge({
        bodySize: body.clientWidth,
        visibleSize: visW,
        fixedEdge: fixedLeft,
        anchor: 'start',
      })
    }
    syncGeometry()
  }

  function applyCropDrag(dx: number, dy: number, body: HTMLElement): void {
    const fullW = baseFitW.value * startScale
    const fullH = baseFitH.value * startScale
    if (fullW <= 0 || fullH <= 0) return
    const edge = cropEdgeForHandle(cropHandle)
    const span = edge === 'left' || edge === 'right' ? fullW : fullH
    const delta = edge === 'left' || edge === 'right' ? dx : dy
    const nextCrop = cropEdgeFromDelta(edge, startCrop, delta, span)
    placeAnchoredCrop(
      edge,
      nextCrop,
      body,
      fullW,
      fullH,
      anchorLeft,
      anchorTop,
      anchorRight,
      anchorBottom
    )
  }

  function onCropKeyDown(event: KeyboardEvent, handle: string): void {
    if (!isCropHandle(handle)) return
    const edge = cropEdgeForHandle(handle)
    const direction = worksheetDiagramCropKeyDelta(edge, event.key)
    if (direction === 0) return
    const body = diagramBodyRef.value
    const scale = clampScale(options.scale.value)
    const fullW = baseFitW.value * scale
    const fullH = baseFitH.value * scale
    if (!body || fullW <= 0 || fullH <= 0) return
    event.preventDefault()
    event.stopPropagation()
    const start = currentCrop()
    const { cw, ch } = worksheetDiagramCropFractions(start)
    const origin = worksheetDiagramFrameOrigin(
      body.clientWidth,
      body.clientHeight,
      fullW * cw,
      fullH * ch,
      clampOffset(options.offsetX.value),
      clampOffset(options.offsetY.value)
    )
    const span = edge === 'left' || edge === 'right' ? fullW : fullH
    const nextCrop = cropEdgeFromDelta(edge, start, direction * CROP_NUDGE * span, span)
    placeAnchoredCrop(
      edge,
      nextCrop,
      body,
      fullW,
      fullH,
      origin.left,
      origin.top,
      origin.right,
      origin.bottom
    )
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

    if (mode === 'crop' && croppingAxis.value) {
      applyCropDrag(dx, dy, body)
      return
    }

    if (mode === 'resize' && resizing.value && startFrameW > 0 && startFrameH > 0) {
      const signedDx = resizeHandle === 'ne' || resizeHandle === 'se' ? dx : -dx
      const signedDy = resizeHandle === 'sw' || resizeHandle === 'se' ? dy : -dy
      const factor = 1 + (signedDx / startFrameW + signedDy / startFrameH) / 2
      const nextScale = clampScale(startScale * factor)
      options.scale.value = nextScale

      const { cw, ch } = worksheetDiagramCropFractions(currentCrop())
      const nextFrameW = baseFitW.value * nextScale * cw
      const nextFrameH = baseFitH.value * nextScale * ch
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
    croppingAxis.value = null
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
    croppingAxis.value = null
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
    croppingAxis,
    diagramAlign,
    showCenterGuideX,
    showCenterGuideY,
    diagramFrameStyle,
    diagramImageStyle,
    onFramePointerDown,
    onFramePointerMove,
    onFramePointerUp: endInteraction,
    onFramePointerCancel: endInteraction,
    onCropKeyDown,
    onDiagramImageLoad,
    syncFreeSpace: syncGeometry,
    resetInteraction,
    alignDiagram,
  }
}
