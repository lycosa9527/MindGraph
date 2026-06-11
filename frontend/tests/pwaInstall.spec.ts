import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  canShowPwaInstallUi,
  isIosAddToHomeScreenEligible,
  isPwaStandalone,
  promptPwaInstall,
} from '@/utils/pwaInstall'

const IPHONE_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
const WINDOWS_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

function mockNavigator(userAgent: string): void {
  vi.stubGlobal('navigator', { userAgent })
}

function mockWindow(options: {
  standalone?: boolean
  displayMode?: string
  innerWidth?: number
  userAgent?: string
}): void {
  const ua = options.userAgent ?? WINDOWS_UA
  vi.stubGlobal('window', {
    innerWidth: options.innerWidth ?? 1280,
    matchMedia: (query: string) => ({
      matches:
        query.includes('standalone') && options.displayMode === 'standalone',
    }),
    navigator: { userAgent: ua, standalone: options.standalone ?? false },
  })
  vi.stubGlobal('navigator', { userAgent: ua, platform: 'Win32', maxTouchPoints: 0 })
}

describe('pwaInstall', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('detects iOS Add to Home Screen eligibility', () => {
    mockNavigator(IPHONE_UA)
    expect(isIosAddToHomeScreenEligible()).toBe(true)

    mockNavigator(WINDOWS_UA)
    expect(isIosAddToHomeScreenEligible()).toBe(false)
  })

  it('hides install UI when already standalone', () => {
    mockNavigator(WINDOWS_UA)
    mockWindow({ displayMode: 'standalone' })
    expect(isPwaStandalone()).toBe(true)
    expect(canShowPwaInstallUi()).toBe(false)
  })

  it('shows install UI on iOS before standalone', () => {
    mockNavigator(IPHONE_UA)
    mockWindow({ displayMode: 'browser' })
    expect(canShowPwaInstallUi()).toBe(true)
  })

  it('shows install UI on desktop Windows before beforeinstallprompt', () => {
    mockWindow({ displayMode: 'browser', innerWidth: 1280, userAgent: WINDOWS_UA })
    expect(canShowPwaInstallUi()).toBe(true)
  })

  it('returns desktop-hint on Chromium when install prompt is not ready', async () => {
    vi.useFakeTimers()
    mockWindow({ displayMode: 'browser', innerWidth: 1280, userAgent: WINDOWS_UA })
    const resultPromise = promptPwaInstall()
    await vi.runAllTimersAsync()
    await expect(resultPromise).resolves.toBe('desktop-hint')
    vi.useRealTimers()
  })

  it('returns ios-hint when prompting on iOS without deferred event', async () => {
    mockNavigator(IPHONE_UA)
    mockWindow({ displayMode: 'browser' })
    await expect(promptPwaInstall()).resolves.toBe('ios-hint')
  })
})
