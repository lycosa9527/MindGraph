/**
 * Classroom IFP / e-blackboard multi-touch classification.
 * No rotate — pinch, pan, swipe, tap, hold, and node slashes.
 */

export const TOUCH_GESTURE = {
  TAP_MAX_MOVE_PX: 12,
  PINCH_DEADZONE_RATIO: 0.08,
  SWIPE_MIN_PX: 80,
  SWIPE_AXIS_RATIO: 1.6,
  MULTI_TAP_MAX_MOVE_PX: 20,
  MULTI_TAP_MAX_MS: 320,
  DOUBLE_TAP_MAX_MS: 320,
  DOUBLE_TAP_MAX_DIST_PX: 28,
  LONG_PRESS_MS: 500,
  /** Fruit-ninja cut: fast stroke through a node, along one axis. */
  SLASH_MIN_PX: 64,
  SLASH_MAX_MS: 700,
  SLASH_MIN_SPEED: 0.35,
  SLASH_AXIS_RATIO: 1.8,
  /** Minimum entry slack, then 35% of the node, never more than 40%. */
  SLASH_EDGE_BAND_PX: 16,
  SLASH_EDGE_BAND_RATIO: 0.35,
  SLASH_EDGE_BAND_CAP_RATIO: 0.4,
  SLASH_HIT_PAD_PX: 10,
  /** Lock the stroke before it finishes so a cut is not also a node drag. */
  SLASH_ARM_PX: 40,
} as const

export type TouchPoint = { x: number; y: number }

export type SwipeAxis = 'left' | 'right' | 'up' | 'down'

export type TwoFingerLock = 'pinch' | 'pan' | 'swipe-h' | 'undecided'

export function touchDistance(a: TouchPoint, b: TouchPoint): number {
  return Math.hypot(b.x - a.x, b.y - a.y)
}

export function touchCentroid(points: TouchPoint[]): TouchPoint {
  if (points.length === 0) {
    return { x: 0, y: 0 }
  }
  let x = 0
  let y = 0
  for (const point of points) {
    x += point.x
    y += point.y
  }
  return { x: x / points.length, y: y / points.length }
}

export function isPinchScale(startDist: number, curDist: number): boolean {
  if (startDist <= 0) {
    return false
  }
  return Math.abs(curDist / startDist - 1) >= TOUCH_GESTURE.PINCH_DEADZONE_RATIO
}

export function classifySwipe(
  dx: number,
  dy: number,
  minPx: number = TOUCH_GESTURE.SWIPE_MIN_PX
): SwipeAxis | null {
  const absX = Math.abs(dx)
  const absY = Math.abs(dy)
  if (absX < minPx && absY < minPx) {
    return null
  }
  if (absX >= absY * TOUCH_GESTURE.SWIPE_AXIS_RATIO && absX >= minPx) {
    return dx < 0 ? 'left' : 'right'
  }
  if (absY >= absX * TOUCH_GESTURE.SWIPE_AXIS_RATIO && absY >= minPx) {
    return dy < 0 ? 'up' : 'down'
  }
  return null
}

export function lockTwoFingerMove(options: {
  startDist: number
  curDist: number
  dx: number
  dy: number
  allowHorizontalSwipe: boolean
  current: TwoFingerLock
}): TwoFingerLock {
  if (options.current !== 'undecided') {
    return options.current
  }
  if (isPinchScale(options.startDist, options.curDist)) {
    return 'pinch'
  }
  const swipe = classifySwipe(options.dx, options.dy)
  if (options.allowHorizontalSwipe && (swipe === 'left' || swipe === 'right')) {
    return 'swipe-h'
  }
  if (Math.hypot(options.dx, options.dy) > TOUCH_GESTURE.TAP_MAX_MOVE_PX) {
    return 'pan'
  }
  return 'undecided'
}

export function isStationaryMultiTap(maxMovePx: number, elapsedMs: number): boolean {
  return (
    maxMovePx <= TOUCH_GESTURE.MULTI_TAP_MAX_MOVE_PX &&
    elapsedMs <= TOUCH_GESTURE.MULTI_TAP_MAX_MS
  )
}

export function isDoubleTap(
  previous: { x: number; y: number; at: number } | null,
  next: { x: number; y: number; at: number }
): boolean {
  if (!previous) {
    return false
  }
  if (next.at - previous.at > TOUCH_GESTURE.DOUBLE_TAP_MAX_MS) {
    return false
  }
  return touchDistance(previous, next) <= TOUCH_GESTURE.DOUBLE_TAP_MAX_DIST_PX
}

/** Desktop IFP / touch laptop: 2-finger pan so 1-finger stays select. */
export function shouldEnableDesktopTouchPanPinch(
  eBlackboardOptimize: boolean,
  maxTouchPoints: number
): boolean {
  return eBlackboardOptimize || maxTouchPoints >= 2
}

export type NodeScreenRect = {
  id: string
  left: number
  top: number
  right: number
  bottom: number
}

function slashEndpoints(points: TouchPoint[]): { dx: number; dy: number } | null {
  if (points.length < 2) return null
  const start = points[0]
  const end = points[points.length - 1]
  return { dx: end.x - start.x, dy: end.y - start.y }
}

export type NodeSlashAction = 'delete' | 'sibling' | 'child'

export type NodeSlashHit = {
  action: NodeSlashAction
  nodeIds: string[]
}

function slashIsFast(points: TouchPoint[], elapsedMs: number): { dx: number; dy: number } | null {
  const delta = slashEndpoints(points)
  if (!delta || elapsedMs <= 0 || elapsedMs > TOUCH_GESTURE.SLASH_MAX_MS) return null
  if (Math.hypot(delta.dx, delta.dy) / elapsedMs < TOUCH_GESTURE.SLASH_MIN_SPEED) return null
  return delta
}

/** Fast axis-locked travel — down, up, or sideways — before it is also a drag. */
export function isNodeSlashTravel(points: TouchPoint[], elapsedMs: number): boolean {
  const delta = slashIsFast(points, elapsedMs)
  if (!delta) return false
  const absX = Math.abs(delta.dx)
  const absY = Math.abs(delta.dy)
  const major = Math.max(absX, absY)
  const minor = Math.min(absX, absY)
  return major >= TOUCH_GESTURE.SLASH_ARM_PX && major >= minor * TOUCH_GESTURE.SLASH_AXIS_RATIO
}

/** Fast, mostly vertical, downward travel — not a slow drag or a sideways swipe. */
export function isDownwardSlashTravel(points: TouchPoint[], elapsedMs: number): boolean {
  const delta = slashIsFast(points, elapsedMs)
  if (!delta || delta.dy < TOUCH_GESTURE.SLASH_ARM_PX) return false
  return delta.dy >= Math.abs(delta.dx) * TOUCH_GESTURE.SLASH_AXIS_RATIO
}

function edgeBand(span: number): number {
  const proportional = span * TOUCH_GESTURE.SLASH_EDGE_BAND_RATIO
  const slack = Math.max(TOUCH_GESTURE.SLASH_EDGE_BAND_PX, proportional)
  return Math.min(span * TOUCH_GESTURE.SLASH_EDGE_BAND_CAP_RATIO, slack)
}

/** Other-axis position where the stroke crosses `at` while moving along `axis`. */
function crossCoord(
  points: TouchPoint[],
  at: number,
  axis: 'x' | 'y',
  direction: 1 | -1
): number | null {
  for (let i = 1; i < points.length; i += 1) {
    const prev = points[i - 1]
    const next = points[i]
    const a = axis === 'y' ? prev.y : prev.x
    const b = axis === 'y' ? next.y : next.x
    if ((b - a) * direction <= 0) continue
    if (at < Math.min(a, b) || at > Math.max(a, b)) continue
    const t = (at - a) / (b - a)
    const otherA = axis === 'y' ? prev.x : prev.y
    const otherB = axis === 'y' ? next.x : next.y
    return otherA + t * (otherB - otherA)
  }
  return null
}

function slashCrossesNode(points: TouchPoint[], rect: NodeScreenRect, action: NodeSlashAction, dx: number): boolean {
  if (points.length < 2) return false
  const start = points[0]
  const end = points[points.length - 1]
  const pad = TOUCH_GESTURE.SLASH_HIT_PAD_PX
  if (action === 'sibling') {
    const width = rect.right - rect.left
    if (width <= 0) return false
    const band = edgeBand(width)
    const leftToRight = dx >= 0
    if (leftToRight && (start.x > rect.left + band || end.x < rect.right - band)) return false
    if (!leftToRight && (start.x < rect.right - band || end.x > rect.left + band)) return false
    const yMid = crossCoord(points, (rect.left + rect.right) / 2, 'x', leftToRight ? 1 : -1)
    return yMid !== null && yMid >= rect.top - pad && yMid <= rect.bottom + pad
  }
  const height = rect.bottom - rect.top
  if (height <= 0) return false
  const band = edgeBand(height)
  const downward = action === 'delete'
  if (downward && (start.y > rect.top + band || end.y < rect.bottom - band)) return false
  if (!downward && (start.y < rect.bottom - band || end.y > rect.top + band)) return false
  const xMid = crossCoord(points, (rect.top + rect.bottom) / 2, 'y', downward ? 1 : -1)
  return xMid !== null && xMid >= rect.left - pad && xMid <= rect.right + pad
}

function slashActionOf(dx: number, dy: number): NodeSlashAction | null {
  const absX = Math.abs(dx)
  const absY = Math.abs(dy)
  if (dy >= TOUCH_GESTURE.SLASH_MIN_PX && dy >= absX * TOUCH_GESTURE.SLASH_AXIS_RATIO) return 'delete'
  if (-dy >= TOUCH_GESTURE.SLASH_MIN_PX && -dy >= absX * TOUCH_GESTURE.SLASH_AXIS_RATIO) return 'child'
  if (absX >= TOUCH_GESTURE.SLASH_MIN_PX && absX >= absY * TOUCH_GESTURE.SLASH_AXIS_RATIO) return 'sibling'
  return null
}

/**
 * What a fast one-finger or left-button cut should do.
 * Down deletes every node it crosses. Up adds a child on the first node.
 * Left or right adds one sibling on the first node. Null when it is not a cut.
 */
export function classifyNodeSlash(
  points: TouchPoint[],
  elapsedMs: number,
  nodes: NodeScreenRect[]
): NodeSlashHit | null {
  const delta = slashIsFast(points, elapsedMs)
  if (!delta) return null
  const action = slashActionOf(delta.dx, delta.dy)
  if (!action) return null
  const crossed = nodes.filter((node) => slashCrossesNode(points, node, action, delta.dx))
  if (crossed.length === 0) return null
  if (action === 'delete') {
    return {
      action,
      nodeIds: crossed
        .sort((a, b) => a.top - b.top || a.left - b.left)
        .map((node) => node.id),
    }
  }
  const first =
    action === 'child'
      ? crossed.sort((a, b) => b.bottom - a.bottom)[0]
      : delta.dx >= 0
        ? crossed.sort((a, b) => a.left - b.left)[0]
        : crossed.sort((a, b) => b.right - a.right)[0]
  if (!first) return null
  return { action, nodeIds: [first.id] }
}

/**
 * Node ids a top-to-bottom cut passed through, topmost first.
 * Empty when the stroke is too slow, too short, or not downward.
 */
export function nodesCutByDownwardSlash(
  points: TouchPoint[],
  elapsedMs: number,
  nodes: NodeScreenRect[]
): string[] {
  const hit = classifyNodeSlash(points, elapsedMs, nodes)
  return hit?.action === 'delete' ? hit.nodeIds : []
}
