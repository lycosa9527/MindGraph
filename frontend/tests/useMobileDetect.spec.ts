import { afterEach, describe, expect, it } from 'vitest'

import { resetClientShellLockForTests, writeClientShellLock } from '@/utils/clientShellLock'
import {
  computeIsMobileClient,
  isSmallViewportWidth,
  isTouchDeviceUserAgent,
} from '@/utils/isMobileClient'
import {
  isOfficeEmbedDesktop,
  resetOfficeEmbedForTests,
  syncOfficeEmbedFromSearch,
} from '@/utils/officeEmbed'

describe('isMobileClient', () => {
  afterEach(() => {
    resetOfficeEmbedForTests()
    resetClientShellLockForTests()
  })

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

  it('keeps a HarmonyOS phone on the touch shell when the inner screen is wide', () => {
    const puraUnfolded =
      'Mozilla/5.0 (Phone; OpenHarmony 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 ArkWeb/4.1.6.1 Mobile'
    expect(isTouchDeviceUserAgent(puraUnfolded)).toBe(true)
    expect(computeIsMobileClient(1220, puraUnfolded)).toBe(true)
  })

  it('leaves a HarmonyOS tablet on the desktop shell when the window is wide', () => {
    const tablet =
      'Mozilla/5.0 (Tablet; OpenHarmony 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 ArkWeb/4.1.6.1'
    expect(isTouchDeviceUserAgent(tablet)).toBe(false)
    expect(computeIsMobileClient(1220, tablet)).toBe(false)
    expect(computeIsMobileClient(360, tablet)).toBe(true)
  })

  it('leaves a HarmonyOS PC on the desktop shell when the window is wide', () => {
    const pc =
      'Mozilla/5.0 (PC; OpenHarmony 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 ArkWeb/4.1.6.1'
    expect(isTouchDeviceUserAgent(pc)).toBe(false)
    expect(computeIsMobileClient(1220, pc)).toBe(false)
  })

  it('treats wide desktop viewport as non-mobile', () => {
    const desktopUa =
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    expect(computeIsMobileClient(1280, desktopUa)).toBe(false)
  })

  it('keeps a locked desktop shell when the tablet rotates to a narrow width', () => {
    const ipadUa =
      'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
    writeClientShellLock('desktop')
    expect(computeIsMobileClient(480, ipadUa)).toBe(false)
    expect(computeIsMobileClient(1280, ipadUa)).toBe(false)
  })

  it('keeps a locked mobile shell on a wide viewport', () => {
    const desktopUa =
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    writeClientShellLock('mobile')
    expect(computeIsMobileClient(1280, desktopUa)).toBe(true)
  })

  it('treats word-addin embed query as desktop even when narrow', () => {
    syncOfficeEmbedFromSearch('?embed=word-addin')
    expect(isOfficeEmbedDesktop()).toBe(true)
    writeClientShellLock('mobile')
    const ipadUa =
      'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
    expect(computeIsMobileClient(480, ipadUa)).toBe(false)
  })
})
