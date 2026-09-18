/**
 * Classroom IFP / e-blackboard multi-touch classification.
 * No rotate — pinch, pan, swipe, tap, and hold only.
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
