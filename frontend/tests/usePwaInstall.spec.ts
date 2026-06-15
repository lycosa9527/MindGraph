import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { usePwaInstall } from '@/composables/usePwaInstall'
import {
  injectDeferredInstallPromptForTests,
  resetPwaInstallStateForTests,
} from '@/utils/pwaInstall'

const WINDOWS_EDGE_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'

const notifySuccess = vi.fn()
const notifyInfo = vi.fn()

vi.mock('@/composables', () => ({
  useNotifications: () => ({
    success: notifySuccess,
    info: notifyInfo,
  }),
}))

function mockDesktopHttps(userAgent: string): void {
  vi.stubGlobal('window', {
    innerWidth: 1440,
    isSecureContext: true,
    location: { protocol: 'https:' },
    matchMedia: () => ({ matches: false }),
    navigator: {
      userAgent,
      platform: 'Win32',
      maxTouchPoints: 0,
      standalone: false,
    },
    setTimeout: globalThis.setTimeout.bind(globalThis),
    clearTimeout: globalThis.clearTimeout.bind(globalThis),
  })
  vi.stubGlobal('navigator', {
    userAgent,
    platform: 'Win32',
    maxTouchPoints: 0,
  })
}

describe('usePwaInstall', () => {
  beforeEach(() => {
    resetPwaInstallStateForTests()
    notifySuccess.mockReset()
    notifyInfo.mockReset()
    mockDesktopHttps(WINDOWS_EDGE_UA)
  })

  afterEach(() => {
    resetPwaInstallStateForTests()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('shows install entry on Windows Edge over HTTPS', () => {
    const { showPwaInstall } = usePwaInstall((key) => key)
    expect(showPwaInstall.value).toBe(true)
  })

  it('shows success toast when install is accepted', async () => {
    injectDeferredInstallPromptForTests('accepted')
    const translate = vi.fn((key: string) => key)
    const { handlePwaInstall } = usePwaInstall(translate)

    await handlePwaInstall()

    expect(notifySuccess).toHaveBeenCalledWith('auth.pwaInstallSuccess')
    expect(notifyInfo).not.toHaveBeenCalled()
  })

  it('shows desktop hint when native prompt is unavailable', async () => {
    vi.useFakeTimers()
    const translate = vi.fn((key: string) => key)
    const { handlePwaInstall } = usePwaInstall(translate)

    const pending = handlePwaInstall()
    await vi.runAllTimersAsync()
    await pending

    expect(notifyInfo).toHaveBeenCalledWith('auth.pwaDesktopInstallHint')
    expect(notifySuccess).not.toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('does not toast when user dismisses install dialog', async () => {
    injectDeferredInstallPromptForTests('dismissed')
    const { handlePwaInstall } = usePwaInstall((key) => key)

    await handlePwaInstall()

    expect(notifySuccess).not.toHaveBeenCalled()
    expect(notifyInfo).not.toHaveBeenCalled()
  })

  it('hides install entry after successful install in the same session', async () => {
    injectDeferredInstallPromptForTests('accepted')
    const { showPwaInstall, handlePwaInstall } = usePwaInstall((key) => key)

    expect(showPwaInstall.value).toBe(true)
    await handlePwaInstall()
    expect(showPwaInstall.value).toBe(false)
  })
})
