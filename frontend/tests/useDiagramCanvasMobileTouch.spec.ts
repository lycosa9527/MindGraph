import { describe, expect, it } from 'vitest'

import {
  computePinchViewport,
  nextTouchGesturePhase,
  PANE_TAP_MAX_MOVE_PX,
} from '@/composables/diagramCanvas/useDiagramCanvasMobileTouch'
import { ANIMATION } from '@/config/uiConfig'

describe('useDiagramCanvasMobileTouch constants', () => {
  it('uses a reasonable pane tap movement threshold', () => {
    expect(PANE_TAP_MAX_MOVE_PX).toBeGreaterThan(0)
    expect(PANE_TAP_MAX_MOVE_PX).toBeLessThanOrEqual(20)
  })

  it('keeps touch branch-move arming shorter than mouse long-press', () => {
    expect(ANIMATION.TOUCH_LONG_PRESS_MS).toBeLessThan(ANIMATION.LONG_PRESS_MS)
    expect(ANIMATION.TOUCH_LONG_PRESS_MS).toBeGreaterThanOrEqual(400)
    expect(ANIMATION.TOUCH_LONG_PRESS_MS).toBeLessThanOrEqual(800)
  })
})

describe('nextTouchGesturePhase', () => {
  it('hands off pinch to pan when one finger remains', () => {
    expect(nextTouchGesturePhase(1, true)).toBe('handoff-pan')
  })

  it('continues an existing single-finger session when not pinching', () => {
    expect(nextTouchGesturePhase(1, false)).toBe('continue')
  })

  it('goes idle when all fingers lift', () => {
    expect(nextTouchGesturePhase(0, true)).toBe('idle')
    expect(nextTouchGesturePhase(0, false)).toBe('idle')
  })

  it('stays in pinch while two or more fingers remain', () => {
    expect(nextTouchGesturePhase(2, true)).toBe('pinch')
    expect(nextTouchGesturePhase(3, false)).toBe('pinch')
  })
})

describe('computePinchViewport', () => {
  it('preserves viewport when scale is 1 and the pinch center does not move', () => {
    const next = computePinchViewport({
      pinchStartDist: 100,
      pinchStartZoom: 1.5,
      pinchStartCenterX: 220,
      pinchStartCenterY: 180,
      pinchStartVpX: 40,
      pinchStartVpY: -20,
      curDist: 100,
      curCenterX: 220,
      curCenterY: 180,
      containerLeft: 20,
      containerTop: 10,
      zoomMin: 0.1,
      zoomMax: 4,
    })
    expect(next.zoom).toBe(1.5)
    expect(next.x).toBe(40)
    expect(next.y).toBe(-20)
  })

  it('doubles zoom about the pinch start center and applies pan delta', () => {
    const next = computePinchViewport({
      pinchStartDist: 100,
      pinchStartZoom: 1,
      pinchStartCenterX: 200,
      pinchStartCenterY: 150,
      pinchStartVpX: 0,
      pinchStartVpY: 0,
      curDist: 200,
      curCenterX: 210,
      curCenterY: 160,
      containerLeft: 0,
      containerTop: 0,
      zoomMin: 0.1,
      zoomMax: 4,
    })
    expect(next.zoom).toBe(2)
    // anchor (200,150), flow (200,150) → 200 - 400 + 10 / 150 - 300 + 10
    expect(next.x).toBe(-190)
    expect(next.y).toBe(-140)
  })

  it('clamps zoom to min/max', () => {
    const tooSmall = computePinchViewport({
      pinchStartDist: 100,
      pinchStartZoom: 1,
      pinchStartCenterX: 0,
      pinchStartCenterY: 0,
      pinchStartVpX: 0,
      pinchStartVpY: 0,
      curDist: 1,
      curCenterX: 0,
      curCenterY: 0,
      containerLeft: 0,
      containerTop: 0,
      zoomMin: 0.5,
      zoomMax: 2,
    })
    expect(tooSmall.zoom).toBe(0.5)

    const tooLarge = computePinchViewport({
      pinchStartDist: 100,
      pinchStartZoom: 1,
      pinchStartCenterX: 0,
      pinchStartCenterY: 0,
      pinchStartVpX: 0,
      pinchStartVpY: 0,
      curDist: 1000,
      curCenterX: 0,
      curCenterY: 0,
      containerLeft: 0,
      containerTop: 0,
      zoomMin: 0.5,
      zoomMax: 2,
    })
    expect(tooLarge.zoom).toBe(2)
  })
})
