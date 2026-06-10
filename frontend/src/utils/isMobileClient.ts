/**
 * Single source of truth for mobile client detection.
 * Matches router redirects: viewport below mobile breakpoint OR touch-class UA.
 */
import { BREAKPOINTS } from '@/config/uiConfig'

const TOUCH_DEVICE_UA =
  /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i

/** True when user agent looks like a phone/tablet touch device. */
export function isTouchDeviceUserAgent(userAgent?: string): boolean {
  const ua =
    userAgent ?? (typeof navigator !== 'undefined' ? navigator.userAgent : '')
  return TOUCH_DEVICE_UA.test(ua)
}

/** True when viewport width is below the mobile breakpoint. */
export function isSmallViewportWidth(width: number): boolean {
  return width < BREAKPOINTS.MOBILE
}

/**
 * Imperative mobile check (resize handlers, one-off calls).
 * Uses current window dimensions when width is omitted.
 */
export function computeIsMobileClient(
  width?: number,
  userAgent?: string
): boolean {
  const resolvedWidth =
    width ??
    (typeof window !== 'undefined' ? window.innerWidth : BREAKPOINTS.MOBILE)
  return (
    isSmallViewportWidth(resolvedWidth) ||
    isTouchDeviceUserAgent(userAgent)
  )
}
