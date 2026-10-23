import { describe, expect, it } from 'vitest'

import { readCanvasInputMode, shouldAttachCanvasTouchLayer } from '@/config/canvasInputMode'
import {
  type NodeScreenRect,
  TOUCH_GESTURE,
  classifyNodeSlash,
  classifySwipe,
  isDoubleTap,
  isNodeSlashTravel,
  isPinchScale,
  isStationaryMultiTap,
  lockTwoFingerMove,
  touchCentroid,
  touchDistance,
} from '@/utils/canvasTouchGestures'

describe('canvasTouchGestures', () => {
  it('measures distance and centroid', () => {
    expect(touchDistance({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5)
    expect(
      touchCentroid([
        { x: 0, y: 0 },
        { x: 10, y: 10 },
      ])
    ).toEqual({ x: 5, y: 5 })
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
    expect(
      isDoubleTap(first, { x: 24, y: 22, at: 1000 + TOUCH_GESTURE.DOUBLE_TAP_MAX_MS + 1 })
    ).toBe(false)
    expect(isDoubleTap(first, { x: 80, y: 80, at: 1100 })).toBe(false)
  })

  it('attaches the touch layer for mobile, the board, and a touch laptop', () => {
    expect(shouldAttachCanvasTouchLayer('board', 0)).toBe(true)
    expect(shouldAttachCanvasTouchLayer('mobile', 0)).toBe(true)
    expect(shouldAttachCanvasTouchLayer('laptop', 2)).toBe(true)
    expect(shouldAttachCanvasTouchLayer('laptop', 0)).toBe(false)
    expect(shouldAttachCanvasTouchLayer('mouse', 2)).toBe(true)
    expect(shouldAttachCanvasTouchLayer('mouse', 0)).toBe(false)
  })

  it('migrates the old classroom toggle and defaults to laptop', () => {
    const storage = {
      getItem(key: string) {
        if (key === 'mindgraph_canvas_input_mode') return null
        if (key === 'mindgraph_e_blackboard_optimize') return '1'
        return null
      },
    }
    expect(readCanvasInputMode(storage)).toBe('board')
    expect(
      readCanvasInputMode({
        getItem: () => null,
      })
    ).toBe('laptop')
  })
})

describe('vertical node slash', () => {
  const node: NodeScreenRect = { id: 'branch-1', left: 100, top: 80, right: 220, bottom: 140 }
  const cut = [
    { x: 160, y: 40 },
    { x: 158, y: 110 },
    { x: 162, y: 190 },
  ]

  it('adds a same-level node when a fast vertical stroke cuts through', () => {
    expect(isNodeSlashTravel(cut, 180)).toBe(true)
    expect(classifyNodeSlash(cut, 180, [node])).toEqual({
      action: 'sibling',
      nodeIds: ['branch-1'],
    })
  })

  it('adds a same-level node on the first node a vertical stroke hits', () => {
    const lower: NodeScreenRect = { id: 'branch-2', left: 90, top: 200, right: 230, bottom: 260 }
    const through = [
      { x: 160, y: 20 },
      { x: 160, y: 300 },
    ]
    expect(classifyNodeSlash(through, 280, [lower, node])).toEqual({
      action: 'sibling',
      nodeIds: ['branch-1'],
    })
    const upward = [...through].reverse()
    expect(classifyNodeSlash(upward, 280, [lower, node])).toEqual({
      action: 'sibling',
      nodeIds: ['branch-2'],
    })
  })

  it('ignores a slow drag and a miss', () => {
    expect(classifyNodeSlash(cut, 900, [node])).toBeNull()
    expect(classifyNodeSlash([...cut].reverse(), 180, [node])?.action).toBe('sibling')
    expect(
      classifyNodeSlash(
        [
          { x: 40, y: 20 },
          { x: 42, y: 200 },
        ],
        180,
        [node]
      )
    ).toBeNull()
  })

  it('ignores a stroke that starts inside the node or stops before the bottom', () => {
    expect(
      classifyNodeSlash(
        [
          { x: 160, y: 120 },
          { x: 160, y: 200 },
        ],
        180,
        [node]
      )
    ).toBeNull()
    expect(
      classifyNodeSlash(
        [
          { x: 160, y: 40 },
          { x: 160, y: 110 },
        ],
        160,
        [node]
      )
    ).toBeNull()
    expect(classifyNodeSlash(cut, 0, [node])).toBeNull()
    expect(isNodeSlashTravel([{ x: 0, y: 0 }], 100)).toBe(false)
  })

  it('keeps the slash faster than a tap', () => {
    expect(TOUCH_GESTURE.SLASH_MIN_PX).toBeGreaterThan(TOUCH_GESTURE.TAP_MAX_MOVE_PX)
    expect(TOUCH_GESTURE.SLASH_MIN_SPEED).toBeGreaterThan(0)
  })
})

describe('node slash actions', () => {
  const node: NodeScreenRect = { id: 'branch-1', left: 100, top: 80, right: 220, bottom: 140 }

  it('deletes every node a sideways cut crosses, either direction', () => {
    const right = [
      { x: 40, y: 110 },
      { x: 280, y: 108 },
    ]
    const left = [...right].reverse()
    const second: NodeScreenRect = { id: 'branch-2', left: 300, top: 80, right: 420, bottom: 140 }
    const across = [
      { x: 20, y: 110 },
      { x: 460, y: 112 },
    ]
    expect(classifyNodeSlash(right, 180, [node])).toEqual({
      action: 'delete',
      nodeIds: ['branch-1'],
    })
    expect(classifyNodeSlash(left, 180, [node])).toEqual({
      action: 'delete',
      nodeIds: ['branch-1'],
    })
    expect(classifyNodeSlash(across, 200, [second, node])).toEqual({
      action: 'delete',
      nodeIds: ['branch-1', 'branch-2'],
    })
    expect(isNodeSlashTravel(right, 180)).toBe(true)
  })

  it('treats an upward cut as a same-level add on the first node', () => {
    const lower: NodeScreenRect = { id: 'branch-2', left: 90, top: 200, right: 230, bottom: 260 }
    const up = [
      { x: 160, y: 300 },
      { x: 160, y: 20 },
    ]
    expect(classifyNodeSlash(up, 220, [node, lower])).toEqual({
      action: 'sibling',
      nodeIds: ['branch-2'],
    })
    expect(isNodeSlashTravel(up, 220)).toBe(true)
  })
})
