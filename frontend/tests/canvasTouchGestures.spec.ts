import { describe, expect, it } from 'vitest'

import {
  classifyNodeSlash,
  classifySwipe,
  isDoubleTap,
  isDownwardSlashTravel,
  isNodeSlashTravel,
  isPinchScale,
  isStationaryMultiTap,
  lockTwoFingerMove,
  nodesCutByDownwardSlash,
  shouldEnableDesktopTouchPanPinch,
  touchCentroid,
  touchDistance,
  TOUCH_GESTURE,
  type NodeScreenRect,
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

describe('downward node slash', () => {
  const node: NodeScreenRect = { id: 'branch-1', left: 100, top: 80, right: 220, bottom: 140 }
  const cut = [
    { x: 160, y: 40 },
    { x: 158, y: 110 },
    { x: 162, y: 190 },
  ]

  it('deletes a node a fast downward stroke cuts through', () => {
    expect(isDownwardSlashTravel(cut, 180)).toBe(true)
    expect(nodesCutByDownwardSlash(cut, 180, [node])).toEqual(['branch-1'])
  })

  it('cuts every node the stroke fully crosses, topmost first', () => {
    const lower: NodeScreenRect = { id: 'branch-2', left: 90, top: 200, right: 230, bottom: 260 }
    const through = [
      { x: 160, y: 20 },
      { x: 160, y: 300 },
    ]
    expect(nodesCutByDownwardSlash(through, 280, [lower, node])).toEqual(['branch-1', 'branch-2'])
  })

  it('ignores a slow drag, an upward stroke, a sideways swipe, and a miss', () => {
    expect(nodesCutByDownwardSlash(cut, 900, [node])).toEqual([])
    expect(nodesCutByDownwardSlash([...cut].reverse(), 180, [node])).toEqual([])
    expect(
      nodesCutByDownwardSlash(
        [
          { x: 40, y: 100 },
          { x: 280, y: 110 },
        ],
        180,
        [node]
      )
    ).toEqual([])
    expect(
      nodesCutByDownwardSlash(
        [
          { x: 40, y: 20 },
          { x: 42, y: 200 },
        ],
        180,
        [node]
      )
    ).toEqual([])
  })

  it('ignores a stroke that starts inside the node or stops before the bottom', () => {
    expect(
      nodesCutByDownwardSlash(
        [
          { x: 160, y: 120 },
          { x: 160, y: 200 },
        ],
        180,
        [node]
      )
    ).toEqual([])
    expect(
      nodesCutByDownwardSlash(
        [
          { x: 160, y: 40 },
          { x: 160, y: 110 },
        ],
        160,
        [node]
      )
    ).toEqual([])
    expect(nodesCutByDownwardSlash(cut, 0, [node])).toEqual([])
    expect(isDownwardSlashTravel([{ x: 0, y: 0 }], 100)).toBe(false)
  })

  it('keeps the slash faster than a tap', () => {
    expect(TOUCH_GESTURE.SLASH_MIN_PX).toBeGreaterThan(TOUCH_GESTURE.TAP_MAX_MOVE_PX)
    expect(TOUCH_GESTURE.SLASH_MIN_SPEED).toBeGreaterThan(0)
  })
})

describe('node slash actions', () => {
  const node: NodeScreenRect = { id: 'branch-1', left: 100, top: 80, right: 220, bottom: 140 }

  it('treats a sideways cut either way as one sibling', () => {
    const right = [
      { x: 40, y: 110 },
      { x: 280, y: 108 },
    ]
    const left = [...right].reverse()
    expect(classifyNodeSlash(right, 180, [node])).toEqual({ action: 'sibling', nodeIds: ['branch-1'] })
    expect(classifyNodeSlash(left, 180, [node])).toEqual({ action: 'sibling', nodeIds: ['branch-1'] })
    expect(isNodeSlashTravel(right, 180)).toBe(true)
    expect(nodesCutByDownwardSlash(right, 180, [node])).toEqual([])
  })

  it('treats an upward cut as a child on the first node', () => {
    const lower: NodeScreenRect = { id: 'branch-2', left: 90, top: 200, right: 230, bottom: 260 }
    const up = [
      { x: 160, y: 300 },
      { x: 160, y: 20 },
    ]
    expect(classifyNodeSlash(up, 220, [node, lower])).toEqual({ action: 'child', nodeIds: ['branch-2'] })
    expect(isDownwardSlashTravel(up, 220)).toBe(false)
  })

  it('keeps a downward cut as delete', () => {
    const down = [
      { x: 160, y: 40 },
      { x: 160, y: 190 },
    ]
    expect(classifyNodeSlash(down, 180, [node])).toEqual({ action: 'delete', nodeIds: ['branch-1'] })
  })
})
