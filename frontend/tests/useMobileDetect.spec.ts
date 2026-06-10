import { describe, expect, it } from 'vitest'

import {
  computeIsMobileClient,
  isSmallViewportWidth,
  isTouchDeviceUserAgent,
} from '@/utils/isMobileClient'

describe('isMobileClient', () => {
  it('detects touch user agents regardless of width', () => {
    const ipadUa =
      'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
    expect(isTouchDeviceUserAgent(ipadUa)).toBe(true)
    expect(computeIsMobileClient(1024, ipadUa)).toBe(true)
  })

  it('detects narrow viewports without touch UA', () => {
    const desktopUa =
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    expect(isTouchDeviceUserAgent(desktopUa)).toBe(false)
    expect(isSmallViewportWidth(767)).toBe(true)
    expect(computeIsMobileClient(767, desktopUa)).toBe(true)
    expect(computeIsMobileClient(768, desktopUa)).toBe(false)
  })

  it('treats wide desktop viewport as non-mobile', () => {
    const desktopUa =
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    expect(computeIsMobileClient(1280, desktopUa)).toBe(false)
  })
})
