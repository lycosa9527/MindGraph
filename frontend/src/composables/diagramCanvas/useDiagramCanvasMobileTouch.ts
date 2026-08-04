import type { Ref } from 'vue'
import { ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import {
  conceptMapLinkChaseActive,
  isTargetOnConceptMapLinkHandle,
} from '@/composables/diagramCanvas/conceptMapLinkChaseState'
import type { useBranchMoveDrag } from '@/composables/editor/useBranchMoveDrag'
import { ZOOM } from '@/config/uiConfig'

/** Panes do not always emit click after touch; dispatch pane-dismiss when the gesture was a tap, not a pan. */
export const PANE_TAP_MAX_MOVE_PX = 12

type BranchMove = ReturnType<typeof useBranchMoveDrag>

type Viewport = { x: number; y: number; zoom: number }

/** Pure pinch→viewport math (exported for unit tests). */
export function computePinchViewport(options: {
  pinchStartDist: number
  pinchStartZoom: number
  pinchStartCenterX: number
  pinchStartCenterY: number
  pinchStartVpX: number
  pinchStartVpY: number
  curDist: number
  curCenterX: number
  curCenterY: number
  containerLeft: number
  containerTop: number
  zoomMin: number
  zoomMax: number
}): Viewport {
  const scale = options.curDist / options.pinchStartDist
  const newZoom = Math.max(
    options.zoomMin,
    Math.min(options.zoomMax, options.pinchStartZoom * scale)
  )
  const anchorX = options.pinchStartCenterX - options.containerLeft
  const anchorY = options.pinchStartCenterY - options.containerTop
  const flowX = (anchorX - options.pinchStartVpX) / options.pinchStartZoom
  const flowY = (anchorY - options.pinchStartVpY) / options.pinchStartZoom
  const panDx = options.curCenterX - options.pinchStartCenterX
  const panDy = options.curCenterY - options.pinchStartCenterY
  return {
    x: anchorX - flowX * newZoom + panDx,
    y: anchorY - flowY * newZoom + panDy,
    zoom: newZoom,
  }
}

/**
 * After a finger lifts, decide the next gesture phase.
 * `handoff-pan`: pinch ended with one finger left — continue as 1-finger pan when allowed.
 * `continue`: one finger left but we were not pinching — keep existing 1-finger session.
 */
export function nextTouchGesturePhase(
  remainingTouches: number,
  wasPinching: boolean
): 'idle' | 'continue' | 'handoff-pan' | 'pinch' {
  if (remainingTouches >= 2) return 'pinch'
  if (remainingTouches === 1 && wasPinching) return 'handoff-pan'
  if (remainingTouches === 1) return 'continue'
  return 'idle'
}

export function useDiagramCanvasMobileTouch(options: {
  canvasContainer: Ref<HTMLElement | null>
  getViewport: () => Viewport
  setViewport: (viewport: Viewport, opts?: { duration?: number }) => void
  branchMove: BranchMove
  /**
   * Phone mobile: true — 1-finger pane pan.
   * Desktop e-blackboard: false — 1-finger is tap/select; 2-finger drag/pinch pans (+ zooms).
   */
  allowSingleFingerPan: () => boolean
}): {
  setupMobileTouchZoom: () => void
  mobileTouchCleanup: Ref<(() => void) | null>
} {
  const { canvasContainer, getViewport, setViewport, branchMove, allowSingleFingerPan } = options
  const mobileTouchCleanup = ref<(() => void) | null>(null)

  function setupMobileTouchZoom(): void {
    if (!canvasContainer.value) return
    const el = canvasContainer.value as HTMLElement

    let pinchStartDist = 0
    let pinchStartZoom = 1
    let pinchStartCenterX = 0
    let pinchStartCenterY = 0
    let pinchStartVpX = 0
    let pinchStartVpY = 0
    let isPinching = false

    let isPanning = false
    let panStartX = 0
    let panStartY = 0
    let panStartVpX = 0
    let panStartVpY = 0
    let panStartZoom = 1
    let singleFingerPaneSession: { hasMoved: boolean } | null = null

    function isOnNode(target: EventTarget | null): boolean {
      if (!(target instanceof HTMLElement)) return false
      return !!target.closest('.vue-flow__node')
    }

    function beginPanFromTouch(touch: Touch, markMoved: boolean): void {
      const vp = getViewport()
      isPanning = true
      singleFingerPaneSession = { hasMoved: markMoved }
      panStartX = touch.clientX
      panStartY = touch.clientY
      panStartVpX = vp.x
      panStartVpY = vp.y
      panStartZoom = vp.zoom
    }

    /** Track 1-finger pane tap without moving the viewport (e-blackboard select UX). */
    function beginPaneTapSession(touch: Touch): void {
      isPanning = false
      singleFingerPaneSession = { hasMoved: false }
      panStartX = touch.clientX
      panStartY = touch.clientY
    }

    function clearPinch(): void {
      isPinching = false
      pinchStartDist = 0
    }

    function resetAllGestureState(): void {
      clearPinch()
      isPanning = false
      singleFingerPaneSession = null
    }

    function onTouchStart(e: TouchEvent): void {
      if (conceptMapLinkChaseActive.value) {
        return
      }
      if (e.touches.length === 1 && isTargetOnConceptMapLinkHandle(e.target)) {
        return
      }
      if (e.touches.length >= 2) {
        singleFingerPaneSession = null
        isPanning = false
        isPinching = true
        const t0 = e.touches[0]
        const t1 = e.touches[1]
        pinchStartDist = Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY)
        pinchStartCenterX = (t0.clientX + t1.clientX) / 2
        pinchStartCenterY = (t0.clientY + t1.clientY) / 2
        const vp = getViewport()
        pinchStartZoom = vp.zoom
        pinchStartVpX = vp.x
        pinchStartVpY = vp.y
        e.stopPropagation()
        return
      }

      if (e.touches.length === 1 && !isOnNode(e.target)) {
        if (branchMove.state.value.active) {
          branchMove.cancelDrag()
          return
        }
        if (allowSingleFingerPan()) {
          beginPanFromTouch(e.touches[0], false)
        } else {
          // E-blackboard: leave 1-finger free for tap/select; do not pan.
          beginPaneTapSession(e.touches[0])
        }
        e.stopPropagation()
      }
    }

    function onTouchMove(e: TouchEvent): void {
      if (conceptMapLinkChaseActive.value) {
        e.preventDefault()
        e.stopPropagation()
        return
      }
      // Two-finger: pan (center move) + zoom (distance). Same gesture covers “2-finger pan”.
      if (isPinching && e.touches.length >= 2 && pinchStartDist > 0) {
        e.preventDefault()
        e.stopPropagation()

        const t0 = e.touches[0]
        const t1 = e.touches[1]
        const rect = el.getBoundingClientRect()
        const next = computePinchViewport({
          pinchStartDist,
          pinchStartZoom,
          pinchStartCenterX,
          pinchStartCenterY,
          pinchStartVpX,
          pinchStartVpY,
          curDist: Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY),
          curCenterX: (t0.clientX + t1.clientX) / 2,
          curCenterY: (t0.clientY + t1.clientY) / 2,
          containerLeft: rect.left,
          containerTop: rect.top,
          zoomMin: ZOOM.MIN,
          zoomMax: ZOOM.MAX,
        })
        setViewport(next, { duration: 0 })
        return
      }

      if (isPanning && e.touches.length === 1) {
        e.preventDefault()
        e.stopPropagation()

        const dx = e.touches[0].clientX - panStartX
        const dy = e.touches[0].clientY - panStartY
        if (singleFingerPaneSession && Math.hypot(dx, dy) > PANE_TAP_MAX_MOVE_PX) {
          singleFingerPaneSession.hasMoved = true
        }
        setViewport(
          { x: panStartVpX + dx, y: panStartVpY + dy, zoom: panStartZoom },
          { duration: 0 }
        )
        return
      }

      // Tap-only session (e-blackboard): track slop so a finger slide is not a pane tap.
      if (singleFingerPaneSession && !isPanning && e.touches.length === 1) {
        const dx = e.touches[0].clientX - panStartX
        const dy = e.touches[0].clientY - panStartY
        if (Math.hypot(dx, dy) > PANE_TAP_MAX_MOVE_PX) {
          singleFingerPaneSession.hasMoved = true
        }
      }
    }

    function onTouchEnd(e: TouchEvent): void {
      const phase = nextTouchGesturePhase(e.touches.length, isPinching)

      if (phase === 'pinch') {
        return
      }

      if (phase === 'handoff-pan' && e.touches.length === 1) {
        clearPinch()
        if (allowSingleFingerPan()) {
          beginPanFromTouch(e.touches[0], true)
        }
        return
      }

      if (phase === 'continue') {
        clearPinch()
        return
      }

      // idle — all fingers up
      if (singleFingerPaneSession && !singleFingerPaneSession.hasMoved) {
        eventBus.emit('canvas:pane_clicked', {})
      }
      resetAllGestureState()
    }

    function onTouchCancel(): void {
      // Interrupted gestures must not synthesize pane taps.
      resetAllGestureState()
    }

    el.addEventListener('touchstart', onTouchStart, { capture: true, passive: true })
    el.addEventListener('touchmove', onTouchMove, { capture: true, passive: false })
    el.addEventListener('touchend', onTouchEnd, { capture: true, passive: true })
    el.addEventListener('touchcancel', onTouchCancel, { capture: true, passive: true })

    mobileTouchCleanup.value = () => {
      el.removeEventListener('touchstart', onTouchStart, { capture: true })
      el.removeEventListener('touchmove', onTouchMove, { capture: true })
      el.removeEventListener('touchend', onTouchEnd, { capture: true })
      el.removeEventListener('touchcancel', onTouchCancel, { capture: true })
    }
  }

  return {
    setupMobileTouchZoom,
    mobileTouchCleanup,
  }
}
