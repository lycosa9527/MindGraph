import type { Ref } from 'vue'
import { ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import {
  conceptMapLinkChaseActive,
  isTargetOnConceptMapLinkHandle,
} from '@/composables/diagramCanvas/conceptMapLinkChaseState'
import type { useBranchMoveDrag } from '@/composables/editor/useBranchMoveDrag'
import { ZOOM } from '@/config/uiConfig'
import {
  classifyNodeSlash,
  classifySwipe,
  isDoubleTap,
  isNodeSlashTravel,
  isStationaryMultiTap,
  lockTwoFingerMove,
  TOUCH_GESTURE,
  type NodeScreenRect,
  type NodeSlashAction,
  type NodeSlashHit,
  type TouchPoint,
  type TwoFingerLock,
} from '@/utils/canvasTouchGestures'

/** Panes do not always emit click after touch; dispatch pane-dismiss when the gesture was a tap, not a pan. */
export const PANE_TAP_MAX_MOVE_PX = TOUCH_GESTURE.TAP_MAX_MOVE_PX

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
): 'idle' | 'continue' | 'handoff-pan' | 'pinch' | 'three' | 'four' {
  if (remainingTouches >= 4) return 'four'
  if (remainingTouches === 3) return 'three'
  if (remainingTouches >= 2) return 'pinch'
  if (remainingTouches === 1 && wasPinching) return 'handoff-pan'
  if (remainingTouches === 1) return 'continue'
  return 'idle'
}

function maxCentroidMove(
  start: { x: number; y: number },
  touches: TouchList
): number {
  if (touches.length === 0) {
    return 0
  }
  let x = 0
  let y = 0
  for (let i = 0; i < touches.length; i += 1) {
    x += touches[i].clientX
    y += touches[i].clientY
  }
  return Math.hypot(x / touches.length - start.x, y / touches.length - start.y)
}

type SlashStroke = { points: TouchPoint[]; startedAt: number }

function isEditableTarget(target: EventTarget | null): boolean {
  return target instanceof Element && Boolean(target.closest('input, textarea, select'))
}

function collectNodeScreenRects(root: HTMLElement): NodeScreenRect[] {
  const rects: NodeScreenRect[] = []
  for (const node of root.querySelectorAll('.vue-flow__node')) {
    if (!(node instanceof HTMLElement)) continue
    const id = node.dataset.id
    if (!id || node.querySelector('input, textarea')) continue
    const rect = node.getBoundingClientRect()
    if (rect.width < 2 || rect.height < 2) continue
    rects.push({
      id,
      left: rect.left,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
    })
  }
  return rects
}

const SLASH_TRAIL_COLOR: Record<NodeSlashAction, string> = {
  delete: '#fb7185',
  sibling: '#14b8a6',
  child: '#22c55e',
}

function flashSlashTrail(host: HTMLElement, points: TouchPoint[], color: string): void {
  if (points.length < 2) return
  const bounds = host.getBoundingClientRect()
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('width', String(bounds.width))
  svg.setAttribute('height', String(bounds.height))
  svg.style.position = 'absolute'
  svg.style.inset = '0'
  svg.style.width = '100%'
  svg.style.height = '100%'
  svg.style.pointerEvents = 'none'
  svg.style.zIndex = '40'
  const start = points[0]
  const end = points[points.length - 1]
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'line')
  line.setAttribute('x1', String(start.x - bounds.left))
  line.setAttribute('y1', String(start.y - bounds.top))
  line.setAttribute('x2', String(end.x - bounds.left))
  line.setAttribute('y2', String(end.y - bounds.top))
  line.setAttribute('stroke', color)
  line.setAttribute('stroke-width', '4')
  line.setAttribute('stroke-linecap', 'round')
  svg.appendChild(line)
  host.appendChild(svg)
  const fade = line.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 280, easing: 'ease-out' })
  fade.onfinish = () => svg.remove()
}

function dispatchContextMenu(touch: Touch, target: EventTarget | null): void {
  if (!(target instanceof Element)) {
    return
  }
  target.dispatchEvent(
    new MouseEvent('contextmenu', {
      bubbles: true,
      cancelable: true,
      clientX: touch.clientX,
      clientY: touch.clientY,
      view: window,
    })
  )
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
  /** Two-finger horizontal swipe flips slides instead of panning. */
  canPageSwipe?: () => boolean
  /** Concept-map pane double-tap adds a node; skip fit-view there. */
  canFitOnDoubleTap?: () => boolean
  /** Left-button slash. Off while the primary button pans (hand tool, phone). */
  allowMouseSlash?: () => boolean
}): {
  setupMobileTouchZoom: () => void
  mobileTouchCleanup: Ref<(() => void) | null>
  setupMouseSlash: () => () => void
} {
  const {
    canvasContainer,
    getViewport,
    setViewport,
    branchMove,
    allowSingleFingerPan,
    canPageSwipe,
    canFitOnDoubleTap,
    allowMouseSlash,
  } = options
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
    let twoFingerLock: TwoFingerLock = 'undecided'
    let twoFingerStartAt = 0
    let twoFingerMaxMove = 0

    let isPanning = false
    let panStartX = 0
    let panStartY = 0
    let panStartVpX = 0
    let panStartVpY = 0
    let panStartZoom = 1
    let singleFingerPaneSession: { hasMoved: boolean } | null = null

    let lastPaneTap: { x: number; y: number; at: number } | null = null
    let longPressTimer: ReturnType<typeof setTimeout> | null = null
    let longPressTouch: Touch | null = null
    let longPressTarget: EventTarget | null = null

    let multiStart: { x: number; y: number; at: number; count: number } | null = null
    let multiLast: { x: number; y: number } | null = null
    let slashStroke: SlashStroke | null = null

    function slashGesturesEnabled(): boolean {
      return !allowSingleFingerPan()
    }

    function appendSlashPoint(x: number, y: number, minGap: number): void {
      if (!slashStroke) return
      const points = slashStroke.points
      const last = points[points.length - 1]
      if (last && Math.hypot(x - last.x, y - last.y) < minGap) return
      points.push({ x, y })
    }

    function isOnNode(target: EventTarget | null): boolean {
      if (!(target instanceof HTMLElement)) return false
      return !!target.closest('.vue-flow__node')
    }

    function clearLongPress(): void {
      if (longPressTimer !== null) {
        clearTimeout(longPressTimer)
        longPressTimer = null
      }
      longPressTouch = null
      longPressTarget = null
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
    function beginPaneTapSession(touch: Touch, target: EventTarget | null): void {
      isPanning = false
      singleFingerPaneSession = { hasMoved: false }
      panStartX = touch.clientX
      panStartY = touch.clientY
      longPressTouch = touch
      longPressTarget = target
      longPressTimer = setTimeout(() => {
        if (!singleFingerPaneSession || singleFingerPaneSession.hasMoved) {
          return
        }
        const held = longPressTouch
        const heldTarget = longPressTarget
        clearLongPress()
        singleFingerPaneSession.hasMoved = true
        if (held) {
          dispatchContextMenu(held, heldTarget)
        }
      }, TOUCH_GESTURE.LONG_PRESS_MS)
    }

    function beginTwoFinger(t0: Touch, t1: Touch): void {
      singleFingerPaneSession = null
      slashStroke = null
      isPanning = false
      clearLongPress()
      isPinching = true
      twoFingerLock = 'undecided'
      twoFingerStartAt = Date.now()
      twoFingerMaxMove = 0
      pinchStartDist = Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY)
      pinchStartCenterX = (t0.clientX + t1.clientX) / 2
      pinchStartCenterY = (t0.clientY + t1.clientY) / 2
      const vp = getViewport()
      pinchStartZoom = vp.zoom
      pinchStartVpX = vp.x
      pinchStartVpY = vp.y
    }

    function beginMultiFinger(touches: TouchList): void {
      singleFingerPaneSession = null
      slashStroke = null
      isPanning = false
      isPinching = false
      clearLongPress()
      pinchStartDist = 0
      twoFingerLock = 'undecided'
      let x = 0
      let y = 0
      for (let i = 0; i < touches.length; i += 1) {
        x += touches[i].clientX
        y += touches[i].clientY
      }
      multiStart = {
        x: x / touches.length,
        y: y / touches.length,
        at: Date.now(),
        count: touches.length,
      }
      multiLast = { x: multiStart.x, y: multiStart.y }
    }

    function applyPinchViewport(t0: Touch, t1: Touch): void {
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
    }

    function clearPinch(): void {
      isPinching = false
      pinchStartDist = 0
      twoFingerLock = 'undecided'
    }

    function resetAllGestureState(): void {
      clearPinch()
      clearLongPress()
      isPanning = false
      singleFingerPaneSession = null
      multiStart = null
      multiLast = null
      slashStroke = null
    }

    /** Commit a node cut. Down deletes, up adds a child, sideways adds a sibling. */
    function takeNodeSlash(changed: TouchList): NodeSlashHit | null {
      const stroke = slashStroke
      slashStroke = null
      if (!stroke || !slashGesturesEnabled()) return null
      const lifted = changed[0]
      if (lifted) {
        const last = stroke.points[stroke.points.length - 1]
        if (!last || Math.hypot(lifted.clientX - last.x, lifted.clientY - last.y) >= 1) {
          stroke.points.push({ x: lifted.clientX, y: lifted.clientY })
        }
      }
      const hit = classifyNodeSlash(
        stroke.points,
        Date.now() - stroke.startedAt,
        collectNodeScreenRects(el)
      )
      if (hit) flashSlashTrail(el, stroke.points, SLASH_TRAIL_COLOR[hit.action])
      return hit
    }

    function finishSingleFingerTap(touch: Touch | undefined): void {
      if (!singleFingerPaneSession || singleFingerPaneSession.hasMoved) {
        resetAllGestureState()
        return
      }
      const now = Date.now()
      const tap = touch
        ? { x: touch.clientX, y: touch.clientY, at: now }
        : { x: panStartX, y: panStartY, at: now }
      if (canFitOnDoubleTap?.() !== false && isDoubleTap(lastPaneTap, tap)) {
        lastPaneTap = null
        eventBus.emit('view:fit_to_canvas_requested', { animate: true, userInitiated: true })
      } else {
        lastPaneTap = tap
        eventBus.emit('canvas:pane_clicked', {})
      }
      resetAllGestureState()
    }

    function finishTwoFinger(touches: TouchList, changed: TouchList): void {
      const elapsed = Date.now() - twoFingerStartAt
      const dx = (touches.length >= 2
        ? (touches[0].clientX + touches[1].clientX) / 2
        : pinchStartCenterX) - pinchStartCenterX
      const dy = (touches.length >= 2
        ? (touches[0].clientY + touches[1].clientY) / 2
        : pinchStartCenterY) - pinchStartCenterY
      const endDx = changed.length > 0
        ? ((changed[0]?.clientX ?? pinchStartCenterX) - pinchStartCenterX)
        : dx
      const endDy = changed.length > 0
        ? ((changed[0]?.clientY ?? pinchStartCenterY) - pinchStartCenterY)
        : dy

      if (twoFingerLock === 'undecided' && isStationaryMultiTap(twoFingerMaxMove, elapsed)) {
        eventBus.emit('view:zoom_set_requested', { zoom: ZOOM.DEFAULT })
        resetAllGestureState()
        return
      }

      if (canPageSwipe?.() && (twoFingerLock === 'swipe-h' || twoFingerLock === 'undecided')) {
        const swipe = classifySwipe(endDx, endDy)
        if (swipe === 'left') {
          eventBus.emit('canvas:slide_next_requested', {})
          resetAllGestureState()
          return
        }
        if (swipe === 'right') {
          eventBus.emit('canvas:slide_prev_requested', {})
          resetAllGestureState()
          return
        }
      }
      resetAllGestureState()
    }

    function finishMultiFinger(remaining: TouchList): void {
      if (!multiStart) {
        resetAllGestureState()
        return
      }
      const elapsed = Date.now() - multiStart.at
      const move = maxCentroidMove(multiStart, remaining)
      const start = multiStart
      if (start.count >= 4 && isStationaryMultiTap(Math.max(move, twoFingerMaxMove), elapsed)) {
        eventBus.emit('mindmap:outline_toggle_requested', {})
        resetAllGestureState()
        return
      }
      if (start.count === 3) {
        const end = multiLast ?? {
          x: remaining.length > 0 ? remaining[0].clientX : start.x,
          y: remaining.length > 0 ? remaining[0].clientY : start.y,
        }
        const swipe = classifySwipe(end.x - start.x, end.y - start.y)
        if (swipe === 'left') {
          eventBus.emit('history:undo_requested', {})
        } else if (swipe === 'right') {
          eventBus.emit('history:redo_requested', {})
        }
      }
      resetAllGestureState()
    }

    function onTouchStart(e: TouchEvent): void {
      if (conceptMapLinkChaseActive.value) {
        return
      }
      if (e.touches.length === 1 && isTargetOnConceptMapLinkHandle(e.target)) {
        return
      }
      if (e.touches.length >= 4) {
        beginMultiFinger(e.touches)
        e.stopPropagation()
        return
      }
      if (e.touches.length === 3) {
        beginMultiFinger(e.touches)
        e.stopPropagation()
        return
      }
      if (e.touches.length >= 2) {
        multiStart = null
        beginTwoFinger(e.touches[0], e.touches[1])
        e.stopPropagation()
        return
      }

      if (
        e.touches.length === 1 &&
        slashGesturesEnabled() &&
        !isEditableTarget(e.target) &&
        !branchMove.state.value.active
      ) {
        const touch = e.touches[0]
        slashStroke = {
          points: [{ x: touch.clientX, y: touch.clientY }],
          startedAt: Date.now(),
        }
      } else {
        slashStroke = null
      }

      if (e.touches.length === 1 && !isOnNode(e.target)) {
        if (branchMove.state.value.active) {
          branchMove.cancelDrag()
          return
        }
        if (allowSingleFingerPan()) {
          beginPanFromTouch(e.touches[0], false)
        } else {
          beginPaneTapSession(e.touches[0], e.target)
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

      if (multiStart && e.touches.length >= 3) {
        e.preventDefault()
        e.stopPropagation()
        twoFingerMaxMove = Math.max(twoFingerMaxMove, maxCentroidMove(multiStart, e.touches))
        let x = 0
        let y = 0
        for (let i = 0; i < e.touches.length; i += 1) {
          x += e.touches[i].clientX
          y += e.touches[i].clientY
        }
        multiLast = { x: x / e.touches.length, y: y / e.touches.length }
        return
      }

      if (isPinching && e.touches.length === 2 && pinchStartDist > 0) {
        e.preventDefault()
        e.stopPropagation()

        const t0 = e.touches[0]
        const t1 = e.touches[1]
        const curDist = Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY)
        const curCenterX = (t0.clientX + t1.clientX) / 2
        const curCenterY = (t0.clientY + t1.clientY) / 2
        const dx = curCenterX - pinchStartCenterX
        const dy = curCenterY - pinchStartCenterY
        twoFingerMaxMove = Math.max(twoFingerMaxMove, Math.hypot(dx, dy))
        twoFingerLock = lockTwoFingerMove({
          startDist: pinchStartDist,
          curDist,
          dx,
          dy,
          allowHorizontalSwipe: Boolean(canPageSwipe?.()),
          current: twoFingerLock,
        })
        if (twoFingerLock === 'swipe-h') {
          return
        }
        applyPinchViewport(t0, t1)
        return
      }

      if (isPanning && e.touches.length === 1) {
        e.preventDefault()
        e.stopPropagation()

        const dx = e.touches[0].clientX - panStartX
        const dy = e.touches[0].clientY - panStartY
        if (singleFingerPaneSession && Math.hypot(dx, dy) > PANE_TAP_MAX_MOVE_PX) {
          singleFingerPaneSession.hasMoved = true
          clearLongPress()
        }
        setViewport(
          { x: panStartVpX + dx, y: panStartVpY + dy, zoom: panStartZoom },
          { duration: 0 }
        )
        return
      }

      if (singleFingerPaneSession && !isPanning && e.touches.length === 1) {
        const dx = e.touches[0].clientX - panStartX
        const dy = e.touches[0].clientY - panStartY
        if (Math.hypot(dx, dy) > PANE_TAP_MAX_MOVE_PX) {
          singleFingerPaneSession.hasMoved = true
          clearLongPress()
        }
      }

      if (slashStroke && !isPanning && !isPinching && !multiStart && e.touches.length === 1) {
        const touch = e.touches[0]
        appendSlashPoint(touch.clientX, touch.clientY, 4)
        if (isNodeSlashTravel(slashStroke.points, Date.now() - slashStroke.startedAt)) {
          e.preventDefault()
          e.stopPropagation()
          branchMove.cancelDrag()
          if (singleFingerPaneSession) {
            singleFingerPaneSession.hasMoved = true
            clearLongPress()
          }
        }
      }
    }

    function onTouchEnd(e: TouchEvent): void {
      const phase = nextTouchGesturePhase(e.touches.length, isPinching)

      if (phase === 'four' || phase === 'three') {
        if (multiStart && e.touches.length === 0) {
          finishMultiFinger(e.changedTouches)
        }
        return
      }

      if (phase === 'pinch') {
        if (e.touches.length === 2) {
          beginTwoFinger(e.touches[0], e.touches[1])
        }
        return
      }

      if (multiStart && e.touches.length === 0) {
        finishMultiFinger(e.changedTouches)
        return
      }

      if (isPinching && e.touches.length === 0) {
        finishTwoFinger(e.touches, e.changedTouches)
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

      if (e.touches.length === 0 && slashStroke) {
        const hit = takeNodeSlash(e.changedTouches)
        if (hit) {
          eventBus.emit('diagram:node_slash_requested', hit)
          e.preventDefault()
          e.stopPropagation()
          resetAllGestureState()
          return
        }
      }

      const lifted = e.changedTouches[0]
      finishSingleFingerTap(lifted)
    }

    function onTouchCancel(): void {
      resetAllGestureState()
    }

    el.addEventListener('touchstart', onTouchStart, { capture: true, passive: true })
    el.addEventListener('touchmove', onTouchMove, { capture: true, passive: false })
    el.addEventListener('touchend', onTouchEnd, { capture: true, passive: false })
    el.addEventListener('touchcancel', onTouchCancel, { capture: true, passive: true })

    mobileTouchCleanup.value = () => {
      clearLongPress()
      el.removeEventListener('touchstart', onTouchStart, { capture: true })
      el.removeEventListener('touchmove', onTouchMove, { capture: true })
      el.removeEventListener('touchend', onTouchEnd, { capture: true })
      el.removeEventListener('touchcancel', onTouchCancel, { capture: true })
    }
  }

  /** Same top-to-bottom cut as the finger slash, with the left mouse button. */
  function setupMouseSlash(): () => void {
    const root = canvasContainer.value
    if (!root) return () => {}
    const el = root
    let stroke: (SlashStroke & { pointerId: number }) | null = null

    function detachWindow(): void {
      window.removeEventListener('pointermove', onPointerMove, true)
      window.removeEventListener('pointerup', onPointerUp, true)
      window.removeEventListener('pointercancel', onPointerUp, true)
    }

    function pushPoint(x: number, y: number, minGap: number): void {
      if (!stroke) return
      const last = stroke.points[stroke.points.length - 1]
      if (last && Math.hypot(x - last.x, y - last.y) < minGap) return
      stroke.points.push({ x, y })
    }

    function onPointerMove(event: PointerEvent): void {
      if (!stroke || event.pointerId !== stroke.pointerId) return
      pushPoint(event.clientX, event.clientY, 4)
      const elapsed = Date.now() - stroke.startedAt
      const hit = classifyNodeSlash(stroke.points, elapsed, collectNodeScreenRects(el))
      if (!hit) return
      event.preventDefault()
      event.stopPropagation()
      branchMove.cancelDrag()
    }

    function onPointerUp(event: PointerEvent): void {
      if (!stroke || event.pointerId !== stroke.pointerId) return
      pushPoint(event.clientX, event.clientY, 1)
      const points = stroke.points
      const elapsed = Date.now() - stroke.startedAt
      stroke = null
      detachWindow()
      const hit = classifyNodeSlash(points, elapsed, collectNodeScreenRects(el))
      if (!hit) return
      flashSlashTrail(el, points, SLASH_TRAIL_COLOR[hit.action])
      window.setTimeout(() => {
        eventBus.emit('diagram:node_slash_requested', hit)
      }, 0)
    }

    function onPointerDown(event: PointerEvent): void {
      if (event.pointerType !== 'mouse' || event.button !== 0) return
      if (allowMouseSlash && !allowMouseSlash()) return
      if (conceptMapLinkChaseActive.value) return
      if (isEditableTarget(event.target) || branchMove.state.value.active) return
      detachWindow()
      stroke = {
        points: [{ x: event.clientX, y: event.clientY }],
        startedAt: Date.now(),
        pointerId: event.pointerId,
      }
      window.addEventListener('pointermove', onPointerMove, true)
      window.addEventListener('pointerup', onPointerUp, true)
      window.addEventListener('pointercancel', onPointerUp, true)
    }

    el.addEventListener('pointerdown', onPointerDown)
    return () => {
      stroke = null
      detachWindow()
      el.removeEventListener('pointerdown', onPointerDown)
    }
  }

  return {
    setupMobileTouchZoom,
    mobileTouchCleanup,
    setupMouseSlash,
  }
}
