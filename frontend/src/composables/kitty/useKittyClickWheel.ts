/**
 * iPod-style click wheel logic for Kitty: rotate to cycle diagram child nodes.
 */
import { computed, ref, watch } from 'vue'

import { pulseDeviceEngage, pulseDeviceSelection } from '@/composables/core/useDeviceVibration'
import { buildKittyChildren } from '@/composables/kitty/kittyDiagramChildren'
import { applyKittySelectionTarget } from '@/composables/kitty/kittySelectionApply'
import { useDiagramStore } from '@/stores/diagram'
import type { DiagramType } from '@/types'

/** Inner hole width/height ratios — touch band is the rectangular frame around the mascot. */
const FRAME_INNER_WIDTH_RATIO = 0.54
const FRAME_INNER_HEIGHT_RATIO = 0.5

function rotationStepDeg(childCount: number): number {
  if (childCount <= 0) {
    return 360
  }
  return 360 / childCount
}

export interface KittyClickWheelChild {
  id: string
  index: number
  text: string
}

export interface UseKittyClickWheelOptions {
  onSelectionChange?: () => void
}

function normalizeAngleDelta(prevRad: number, nextRad: number): number {
  let delta = nextRad - prevRad
  while (delta > Math.PI) {
    delta -= 2 * Math.PI
  }
  while (delta < -Math.PI) {
    delta += 2 * Math.PI
  }
  return delta
}

function pointerAngleRad(clientX: number, clientY: number, rect: DOMRect): number {
  const cx = rect.left + rect.width / 2
  const cy = rect.top + rect.height / 2
  return Math.atan2(clientY - cy, clientX - cx)
}

function isOnFrameRing(
  clientX: number,
  clientY: number,
  rect: DOMRect,
  innerWidthRatio: number,
  innerHeightRatio: number
): boolean {
  const x = clientX - rect.left
  const y = clientY - rect.top
  const w = rect.width
  const h = rect.height
  if (x < 0 || y < 0 || x > w || y > h) {
    return false
  }
  const innerLeft = (w * (1 - innerWidthRatio)) / 2
  const innerTop = (h * (1 - innerHeightRatio)) / 2
  const innerRight = w - innerLeft
  const innerBottom = h - innerTop
  if (x >= innerLeft && x <= innerRight && y >= innerTop && y <= innerBottom) {
    return false
  }
  return true
}

export function useKittyClickWheel(options: UseKittyClickWheelOptions = {}) {
  const diagramStore = useDiagramStore()

  const wheelRotationDeg = ref(0)
  const activeIndex = ref(0)
  const isDragging = ref(false)

  let dragStartAngle: number | null = null
  let accumulatedDeg = 0

  const children = computed<KittyClickWheelChild[]>(() => {
    const dt = (diagramStore.type ?? 'circle_map') as DiagramType
    const nodes = diagramStore.data?.nodes ?? []
    return buildKittyChildren(dt, nodes)
  })

  const hasNodes = computed(() => children.value.length > 0)

  const activeChild = computed(() => {
    const list = children.value
    if (list.length === 0) {
      return null
    }
    const idx = Math.min(Math.max(activeIndex.value, 0), list.length - 1)
    return list[idx] ?? null
  })

  function syncIndexFromSelection(): void {
    const list = children.value
    if (list.length === 0) {
      activeIndex.value = 0
      return
    }
    const selectedId = diagramStore.selectedNodes[0]
    if (!selectedId) {
      activeIndex.value = 0
      wheelRotationDeg.value = 0
      return
    }
    const found = list.findIndex((c) => c.id === selectedId)
    if (found >= 0) {
      activeIndex.value = found
      wheelRotationDeg.value = -(360 / list.length) * found
    }
  }

  function selectIndex(nextIndex: number): void {
    const list = children.value
    if (list.length === 0) {
      return
    }
    const wrapped =
      ((nextIndex % list.length) + list.length) % list.length
    if (wrapped === activeIndex.value) {
      return
    }
    activeIndex.value = wrapped
    const child = list[wrapped]
    if (!child) {
      return
    }
    applyKittySelectionTarget({ nodeId: child.id }, { canvasHighlight: false })
    pulseDeviceSelection()
    options.onSelectionChange?.()
  }

  function applyRotationDelta(deltaDeg: number): void {
    if (Math.abs(deltaDeg) < 0.05) {
      return
    }
    wheelRotationDeg.value += deltaDeg
    accumulatedDeg += deltaDeg
    const stepDeg = rotationStepDeg(children.value.length)
    while (Math.abs(accumulatedDeg) >= stepDeg) {
      const steps = Math.trunc(accumulatedDeg / stepDeg)
      accumulatedDeg -= steps * stepDeg
      selectIndex(activeIndex.value - steps)
    }
  }

  function onWheelRingPointerDown(ev: PointerEvent, wheelEl: HTMLElement): void {
    if (!hasNodes.value) {
      return
    }
    const rect = wheelEl.getBoundingClientRect()
    if (
      !isOnFrameRing(
        ev.clientX,
        ev.clientY,
        rect,
        FRAME_INNER_WIDTH_RATIO,
        FRAME_INNER_HEIGHT_RATIO
      )
    ) {
      return
    }
    isDragging.value = true
    dragStartAngle = pointerAngleRad(ev.clientX, ev.clientY, rect)
    accumulatedDeg = 0
    pulseDeviceEngage()
    wheelEl.setPointerCapture(ev.pointerId)
    ev.preventDefault()
  }

  function onWheelRingPointerMove(ev: PointerEvent, wheelEl: HTMLElement): void {
    if (!isDragging.value || dragStartAngle === null) {
      return
    }
    const rect = wheelEl.getBoundingClientRect()
    const angle = pointerAngleRad(ev.clientX, ev.clientY, rect)
    const deltaRad = normalizeAngleDelta(dragStartAngle, angle)
    dragStartAngle = angle
    applyRotationDelta((deltaRad * 180) / Math.PI)
    ev.preventDefault()
  }

  function onWheelRingPointerUp(ev: PointerEvent, wheelEl: HTMLElement): void {
    if (!isDragging.value) {
      return
    }
    isDragging.value = false
    dragStartAngle = null
    accumulatedDeg = 0
    if (wheelEl.hasPointerCapture(ev.pointerId)) {
      wheelEl.releasePointerCapture(ev.pointerId)
    }
  }

  function onWheelRingWheel(ev: WheelEvent): void {
    if (!hasNodes.value) {
      return
    }
    ev.preventDefault()
    const delta = ev.deltaY !== 0 ? ev.deltaY : ev.deltaX
    applyRotationDelta(delta * 0.35)
  }

  function tickRotationDeg(index: number, total: number): number {
    if (total <= 0) {
      return 0
    }
    return (360 / total) * index
  }

  watch(
    () => [children.value.length, diagramStore.selectedNodes.join(',')] as const,
    () => {
      syncIndexFromSelection()
    },
    { immediate: true }
  )

  return {
    children,
    hasNodes,
    activeIndex,
    activeChild,
    wheelRotationDeg,
    isDragging,
    onWheelRingPointerDown,
    onWheelRingPointerMove,
    onWheelRingPointerUp,
    onWheelRingWheel,
    tickRotationDeg,
    selectIndex,
  }
}

export type KittyClickWheelApi = ReturnType<typeof useKittyClickWheel>
