import { describe, expect, it } from 'vitest'

import {
  classifySwipe,
  isDoubleTap,
  isPinchScale,
  isStationaryMultiTap,
  lockTwoFingerMove,
  shouldEnableDesktopTouchPanPinch,
  touchCentroid,
  touchDistance,
  TOUCH_GESTURE,
} from '@/utils/canvasTouchGestures'

describe('canvasTouchGestures', () => {
  it('measures distance and centroid', () => {
    expect(touchDistance({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5)
    expect(touchCentroid([{ x: 0, y: 0 }, { x: 10, y: 10 }])).toEqual({ x: 5, y: 5 })
    expect(touchCentroid([])).toEqual({ x: 0, y: 0 })
  })

  it('treats small scale change as not a pinch', () => {
    expect(isPinchScale(100, 104)).toBe(false)
    expect(isPinchScale(100, 120)).toBe(true)
    expect(isPinchScale(0, 50)).toBe(false)
  })

  it('classifies axis-locked swipes and rejects diagonals', () => {
    expect(classifySwipe(-120, 10)).toBe('left')
    expect(classifySwipe(120, -8)).toBe('right')
    expect(classifySwipe(5, -120)).toBe('up')
    expect(classifySwipe(-4, 120)).toBe('down')
    expect(classifySwipe(40, 10)).toBeNull()
    expect(classifySwipe(90, 80)).toBeNull()
  })

  it('locks two-finger intent: pinch wins, then swipe, then pan', () => {
    expect(
      lockTwoFingerMove({
        startDist: 100,
        curDist: 130,
        dx: 90,
        dy: 0,
        allowHorizontalSwipe: true,
        current: 'undecided',
      })
    ).toBe('pinch')

    expect(
      lockTwoFingerMove({
        startDist: 100,
        curDist: 102,
        dx: -100,
        dy: 4,
        allowHorizontalSwipe: true,
        current: 'undecided',
      })
    ).toBe('swipe-h')

    expect(
      lockTwoFingerMove({
        startDist: 100,
        curDist: 102,
        dx: -100,
        dy: 4,
        allowHorizontalSwipe: false,
        current: 'undecided',
      })
    ).toBe('pan')

    expect(
      lockTwoFingerMove({
        startDist: 100,
        curDist: 130,
        dx: 0,
        dy: 0,
        allowHorizontalSwipe: true,
        current: 'pan',
      })
    ).toBe('pan')
  })

  it('detects stationary multi-finger taps and double taps', () => {
    expect(isStationaryMultiTap(8, 200)).toBe(true)
    expect(isStationaryMultiTap(40, 200)).toBe(false)
    expect(isStationaryMultiTap(8, 800)).toBe(false)

    const first = { x: 20, y: 20, at: 1000 }
    expect(isDoubleTap(null, first)).toBe(false)
    expect(isDoubleTap(first, { x: 24, y: 22, at: 1200 })).toBe(true)
    expect(isDoubleTap(first, { x: 24, y: 22, at: 1000 + TOUCH_GESTURE.DOUBLE_TAP_MAX_MS + 1 })).toBe(
      false
    )
    expect(isDoubleTap(first, { x: 80, y: 80, at: 1100 })).toBe(false)
  })

  it('enables desktop 2-finger layer on e-blackboard or multi-touch hardware', () => {
    expect(shouldEnableDesktopTouchPanPinch(true, 0)).toBe(true)
    expect(shouldEnableDesktopTouchPanPinch(false, 2)).toBe(true)
    expect(shouldEnableDesktopTouchPanPinch(false, 1)).toBe(false)
  })
})
