/**
 * Windows / macOS PWA install matrix — regression guard for desktop browsers.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  canShowPwaInstallUi,
  detectPwaInstallSurface,
  injectDeferredInstallPromptForTests,
  isInstallablePwaOrigin,
  isIosDevice,
  isPwaStandalone,
  promptPwaInstall,
  resetPwaInstallStateForTests,
  type PwaInstallSurface,
} from '@/utils/pwaInstall'

const PLATFORMS = {
  windowsChrome:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  windowsEdge:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
  windowsFirefox:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
  windowsBrave:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Brave/131.0.0.0',
  macChrome:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  macEdge:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
  macSafari:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15',
  macFirefox:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0',
} as const

type PlatformCase = {
  label: string
  userAgent: string
  platform: string
  surface: PwaInstallSurface
  showUi: boolean
  hint?: 'desktop-hint' | 'safari-macos-hint' | 'unavailable'
}

const DESKTOP_MATRIX: PlatformCase[] = [
  {
    label: 'Windows Chrome',
    userAgent: PLATFORMS.windowsChrome,
    platform: 'Win32',
    surface: 'chromium',
    showUi: true,
    hint: 'desktop-hint',
  },
  {
    label: 'Windows Edge',
    userAgent: PLATFORMS.windowsEdge,
    platform: 'Win32',
    surface: 'chromium',
    showUi: true,
    hint: 'desktop-hint',
  },
  {
    label: 'Windows Brave',
    userAgent: PLATFORMS.windowsBrave,
    platform: 'Win32',
    surface: 'chromium',
    showUi: true,
    hint: 'desktop-hint',
  },
  {
    label: 'Windows Firefox',
    userAgent: PLATFORMS.windowsFirefox,
    platform: 'Win32',
    surface: 'firefox',
    showUi: false,
    hint: 'unavailable',
  },
  {
    label: 'macOS Chrome',
    userAgent: PLATFORMS.macChrome,
    platform: 'MacIntel',
    surface: 'chromium',
    showUi: true,
    hint: 'desktop-hint',
  },
  {
    label: 'macOS Edge',
    userAgent: PLATFORMS.macEdge,
    platform: 'MacIntel',
    surface: 'chromium',
    showUi: true,
    hint: 'desktop-hint',
  },
  {
    label: 'macOS Safari',
    userAgent: PLATFORMS.macSafari,
    platform: 'MacIntel',
    surface: 'safari-macos',
    showUi: true,
    hint: 'safari-macos-hint',
  },
  {
    label: 'macOS Firefox',
    userAgent: PLATFORMS.macFirefox,
    platform: 'MacIntel',
    surface: 'firefox',
    showUi: false,
    hint: 'unavailable',
  },
]

function mockDesktopWindow(options: {
  userAgent: string
  platform: string
  protocol?: string
  secureContext?: boolean
  displayMode?: string
  maxTouchPoints?: number
}): void {
  const protocol = options.protocol ?? 'https:'
  vi.stubGlobal('window', {
    innerWidth: 1440,
    isSecureContext: options.secureContext ?? true,
    location: { protocol },
    matchMedia: (query: string) => ({
      matches: Boolean(
        options.displayMode && query.includes(`display-mode: ${options.displayMode}`)
      ),
    }),
    navigator: {
      userAgent: options.userAgent,
      platform: options.platform,
      maxTouchPoints: options.maxTouchPoints ?? 0,
      standalone: false,
    },
    setTimeout: globalThis.setTimeout.bind(globalThis),
    clearTimeout: globalThis.clearTimeout.bind(globalThis),
  })
  vi.stubGlobal('navigator', {
    userAgent: options.userAgent,
    platform: options.platform,
    maxTouchPoints: options.maxTouchPoints ?? 0,
  })
}

describe('pwaInstall desktop platforms (Windows / macOS)', () => {
  afterEach(() => {
    resetPwaInstallStateForTests()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it.each(DESKTOP_MATRIX)(
    '$label detects surface and install UI eligibility',
    ({ userAgent, platform, surface, showUi }) => {
      mockDesktopWindow({ userAgent, platform })
      expect(detectPwaInstallSurface()).toBe(surface)
      expect(canShowPwaInstallUi()).toBe(showUi)
    }
  )

  it.each(DESKTOP_MATRIX.filter((row) => row.hint && row.showUi))(
    '$label returns expected hint without deferred prompt',
    async ({ userAgent, platform, hint }) => {
      vi.useFakeTimers()
      mockDesktopWindow({ userAgent, platform })
      const resultPromise = promptPwaInstall()
      await vi.runAllTimersAsync()
      await expect(resultPromise).resolves.toBe(hint)
      vi.useRealTimers()
    }
  )

  it('macOS Safari is not mis-detected as iOS (maxTouchPoints = 0)', () => {
    mockDesktopWindow({
      userAgent: PLATFORMS.macSafari,
      platform: 'MacIntel',
      maxTouchPoints: 0,
    })
    expect(isIosDevice()).toBe(false)
    expect(detectPwaInstallSurface()).toBe('safari-macos')
  })

  it('macOS Edge on file:// must not offer install (Downloads HTML regression)', () => {
    mockDesktopWindow({
      userAgent: PLATFORMS.macEdge,
      platform: 'MacIntel',
      protocol: 'file:',
      secureContext: true,
    })
    expect(isInstallablePwaOrigin()).toBe(false)
    expect(canShowPwaInstallUi()).toBe(false)
  })

  it('Windows Edge accepts native install when beforeinstallprompt is captured', async () => {
    mockDesktopWindow({
      userAgent: PLATFORMS.windowsEdge,
      platform: 'Win32',
    })
    injectDeferredInstallPromptForTests('accepted')
    expect(canShowPwaInstallUi()).toBe(true)
    await expect(promptPwaInstall()).resolves.toBe('installed')
    expect(canShowPwaInstallUi()).toBe(false)
  })

  it('macOS Edge dismisses native install without error', async () => {
    mockDesktopWindow({
      userAgent: PLATFORMS.macEdge,
      platform: 'MacIntel',
    })
    injectDeferredInstallPromptForTests('dismissed')
    await expect(promptPwaInstall()).resolves.toBe('dismissed')
  })

  it('Windows PWA standalone (window-controls-overlay) hides install UI', () => {
    mockDesktopWindow({
      userAgent: PLATFORMS.windowsEdge,
      platform: 'Win32',
      displayMode: 'window-controls-overlay',
    })
    expect(isPwaStandalone()).toBe(true)
    expect(canShowPwaInstallUi()).toBe(false)
  })

  it.each([
    { label: 'localhost HTTP', protocol: 'http:', secureContext: true },
    { label: '127.0.0.1 HTTP', protocol: 'http:', secureContext: true },
    { label: 'HTTPS', protocol: 'https:', secureContext: true },
  ])('$label is an installable origin on Windows Chrome', ({ protocol, secureContext }) => {
    mockDesktopWindow({
      userAgent: PLATFORMS.windowsChrome,
      platform: 'Win32',
      protocol,
      secureContext,
    })
    expect(isInstallablePwaOrigin()).toBe(true)
    expect(canShowPwaInstallUi()).toBe(true)
  })

  it('LAN HTTP without secure context is blocked on macOS Edge', () => {
    mockDesktopWindow({
      userAgent: PLATFORMS.macEdge,
      platform: 'MacIntel',
      protocol: 'http:',
      secureContext: false,
    })
    expect(isInstallablePwaOrigin()).toBe(false)
    expect(canShowPwaInstallUi()).toBe(false)
  })
})
