import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  bindPwaInstallListeners,
  canShowPwaInstallUi,
  detectPwaInstallSurface,
  getPwaInstallFeedback,
  injectDeferredInstallPromptForTests,
  isInstallablePwaOrigin,
  isIosAddToHomeScreenEligible,
  isIosDevice,
  isPwaStandalone,
  promptPwaInstall,
  resetPwaInstallStateForTests,
} from '@/utils/pwaInstall'

const IPHONE_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
const IPAD_DESKTOP_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
const ANDROID_UA =
  'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
const WINDOWS_CHROME_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
const MAC_EDGE_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
const MAC_SAFARI_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
const FIREFOX_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'

function mockNavigator(
  userAgent: string,
  options: { platform?: string; maxTouchPoints?: number } = {}
): void {
  vi.stubGlobal('navigator', {
    userAgent,
    platform: options.platform ?? 'Win32',
    maxTouchPoints: options.maxTouchPoints ?? 0,
  })
}

function browserTimerFns(): Pick<Window, 'setTimeout' | 'clearTimeout'> {
  return {
    setTimeout: globalThis.setTimeout.bind(globalThis),
    clearTimeout: globalThis.clearTimeout.bind(globalThis),
  }
}

function mockWindow(options: {
  standalone?: boolean
  displayMode?: string
  innerWidth?: number
  userAgent?: string
  protocol?: string
  secureContext?: boolean
  platform?: string
  maxTouchPoints?: number
}): void {
  const ua = options.userAgent ?? WINDOWS_CHROME_UA
  const protocol = options.protocol ?? 'https:'
  vi.stubGlobal('window', {
    innerWidth: options.innerWidth ?? 1280,
    isSecureContext: options.secureContext ?? true,
    location: { protocol },
    matchMedia: (query: string) => ({
      matches: STANDALONE_MEDIA_MATCHES(query, options.displayMode),
    }),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    navigator: {
      userAgent: ua,
      standalone: options.standalone ?? false,
      platform: options.platform ?? 'Win32',
      maxTouchPoints: options.maxTouchPoints ?? 0,
    },
    ...browserTimerFns(),
  })
  mockNavigator(ua, {
    platform: options.platform,
    maxTouchPoints: options.maxTouchPoints,
  })
}

function STANDALONE_MEDIA_MATCHES(query: string, displayMode?: string): boolean {
  if (!displayMode) {
    return false
  }
  return query.includes(`display-mode: ${displayMode}`)
}

describe('pwaInstall', () => {
  afterEach(() => {
    resetPwaInstallStateForTests()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('detects iOS Add to Home Screen eligibility', () => {
    mockWindow({ displayMode: 'browser', userAgent: IPHONE_UA })
    expect(isIosAddToHomeScreenEligible()).toBe(true)

    mockWindow({ displayMode: 'browser', userAgent: WINDOWS_CHROME_UA })
    expect(isIosAddToHomeScreenEligible()).toBe(false)
  })

  it('detects iPadOS desktop site mode as iOS', () => {
    mockNavigator(IPAD_DESKTOP_UA, { platform: 'MacIntel', maxTouchPoints: 5 })
    mockWindow({
      userAgent: IPAD_DESKTOP_UA,
      platform: 'MacIntel',
      maxTouchPoints: 5,
    })
    expect(isIosDevice()).toBe(true)
    expect(detectPwaInstallSurface()).toBe('ios')
    expect(canShowPwaInstallUi()).toBe(true)
  })

  it('hides install UI when already standalone', () => {
    mockWindow({ displayMode: 'standalone', userAgent: WINDOWS_CHROME_UA })
    expect(isPwaStandalone()).toBe(true)
    expect(canShowPwaInstallUi()).toBe(false)
  })

  it('shows install UI on iOS before standalone', () => {
    mockWindow({ displayMode: 'browser', userAgent: IPHONE_UA })
    expect(canShowPwaInstallUi()).toBe(true)
  })

  it('shows install UI on Android', () => {
    mockWindow({ displayMode: 'browser', userAgent: ANDROID_UA, innerWidth: 412 })
    expect(detectPwaInstallSurface()).toBe('android')
    expect(canShowPwaInstallUi()).toBe(true)
  })

  it('shows install UI on desktop Chromium before beforeinstallprompt', () => {
    mockWindow({ displayMode: 'browser', innerWidth: 1280, userAgent: WINDOWS_CHROME_UA })
    expect(detectPwaInstallSurface()).toBe('chromium')
    expect(canShowPwaInstallUi()).toBe(true)
  })

  it('shows install UI on macOS Edge and Safari', () => {
    mockWindow({ displayMode: 'browser', userAgent: MAC_EDGE_UA, platform: 'MacIntel' })
    expect(detectPwaInstallSurface()).toBe('chromium')

    mockWindow({ displayMode: 'browser', userAgent: MAC_SAFARI_UA, platform: 'MacIntel' })
    expect(detectPwaInstallSurface()).toBe('safari-macos')
    expect(canShowPwaInstallUi()).toBe(true)
  })

  it('hides install UI on desktop Firefox', () => {
    mockWindow({ displayMode: 'browser', userAgent: FIREFOX_UA })
    expect(detectPwaInstallSurface()).toBe('firefox')
    expect(canShowPwaInstallUi()).toBe(false)
  })

  it('adopts an install prompt captured before the app bundle loads', () => {
    mockWindow({ displayMode: 'browser', innerWidth: 1280, userAgent: WINDOWS_CHROME_UA })
    window.__mgPwaInstallEarly = {
      prompt: () => Promise.resolve(),
      userChoice: Promise.resolve({ outcome: 'accepted' }),
    } as BeforeInstallPromptEvent
    bindPwaInstallListeners()
    expect(canShowPwaInstallUi()).toBe(true)
    expect(window.__mgPwaInstallEarly).toBeNull()
  })

  it('returns desktop-hint on Chromium when install prompt is not ready', async () => {
    mockWindow({ displayMode: 'browser', innerWidth: 1280, userAgent: WINDOWS_CHROME_UA })
    await expect(promptPwaInstall()).resolves.toBe('desktop-hint')
  })

  it('returns ios-hint when prompting on iOS without deferred event', async () => {
    mockWindow({ displayMode: 'browser', userAgent: IPHONE_UA })
    await expect(promptPwaInstall()).resolves.toBe('ios-hint')
  })

  it('returns android-hint when prompting on Android without deferred event', async () => {
    mockWindow({ displayMode: 'browser', userAgent: ANDROID_UA, innerWidth: 412 })
    await expect(promptPwaInstall()).resolves.toBe('android-hint')
  })

  it('returns safari-macos-hint on Safari macOS without deferred event', async () => {
    mockWindow({ displayMode: 'browser', userAgent: MAC_SAFARI_UA, platform: 'MacIntel' })
    await expect(promptPwaInstall()).resolves.toBe('safari-macos-hint')
  })

  it('hides install UI on file origins', () => {
    mockWindow({ displayMode: 'browser', protocol: 'file:', secureContext: true })
    expect(isInstallablePwaOrigin()).toBe(false)
    expect(canShowPwaInstallUi()).toBe(false)
  })

  it('returns insecure-hint when prompting from a file origin', async () => {
    mockWindow({ displayMode: 'browser', protocol: 'file:', secureContext: true })
    await expect(promptPwaInstall()).resolves.toBe('insecure-hint')
  })

  it('hides install UI on insecure http origins', () => {
    mockWindow({
      displayMode: 'browser',
      protocol: 'http:',
      secureContext: false,
    })
    expect(isInstallablePwaOrigin()).toBe(false)
    expect(canShowPwaInstallUi()).toBe(false)
  })

  it('maps install results to feedback message keys', () => {
    expect(getPwaInstallFeedback('installed')).toEqual({
      kind: 'success',
      messageKey: 'auth.pwaInstallSuccess',
    })
    expect(getPwaInstallFeedback('android-hint')).toEqual({
      kind: 'info',
      messageKey: 'auth.pwaAndroidInstallHint',
    })
    expect(getPwaInstallFeedback('dismissed')).toBeNull()
  })
})
