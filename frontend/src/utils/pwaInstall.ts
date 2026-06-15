/**
 * PWA install helpers — cross-browser / cross-OS detection, prompt capture, UI eligibility.
 */
import { readonly, ref } from 'vue'

import { computeIsMobileClient } from '@/utils/isMobileClient'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

const INSTALL_PROMPT_WAIT_MS = import.meta.env.MODE === 'test' ? 0 : 1500

const STANDALONE_DISPLAY_MODES = [
  'standalone',
  'window-controls-overlay',
  'fullscreen',
  'minimal-ui',
] as const

const installAvailable = ref(false)
const sessionInstalled = ref(false)
let deferredPrompt: BeforeInstallPromptEvent | null = null
let listenersBound = false
const installPromptWaiters: Array<() => void> = []

export const pwaInstallAvailable = readonly(installAvailable)

export type PwaInstallSurface =
  | 'chromium'
  | 'ios'
  | 'android'
  | 'safari-macos'
  | 'firefox'
  | 'unknown'

export type PwaInstallResult =
  | 'installed'
  | 'dismissed'
  | 'unavailable'
  | 'ios-hint'
  | 'android-hint'
  | 'safari-macos-hint'
  | 'desktop-hint'
  | 'dev-hint'
  | 'insecure-hint'

function notifyInstallPromptWaiters(): void {
  while (installPromptWaiters.length > 0) {
    const resolve = installPromptWaiters.pop()
    resolve?.()
  }
}

function captureInstallPrompt(event: Event): void {
  event.preventDefault()
  deferredPrompt = event as BeforeInstallPromptEvent
  installAvailable.value = true
  notifyInstallPromptWaiters()
}

/** @internal Reset captured install state between Vitest cases. */
export function resetPwaInstallStateForTests(): void {
  deferredPrompt = null
  installAvailable.value = false
  sessionInstalled.value = false
  installPromptWaiters.length = 0
}

/** @internal Inject a deferred install prompt for Vitest. */
export function injectDeferredInstallPromptForTests(
  outcome: 'accepted' | 'dismissed'
): void {
  deferredPrompt = {
    prompt: () => Promise.resolve(),
    userChoice: Promise.resolve({ outcome }),
  } as BeforeInstallPromptEvent
  installAvailable.value = true
}

export function bindPwaInstallListeners(): void {
  if (listenersBound || typeof window === 'undefined') {
    return
  }
  listenersBound = true

  window.addEventListener('beforeinstallprompt', captureInstallPrompt)

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null
    installAvailable.value = false
    sessionInstalled.value = true
  })
}

function waitForInstallPrompt(timeoutMs: number): Promise<boolean> {
  if (deferredPrompt) {
    return Promise.resolve(true)
  }
  if (typeof window === 'undefined') {
    return Promise.resolve(false)
  }
  if (typeof window.setTimeout !== 'function') {
    return Promise.resolve(deferredPrompt !== null)
  }
  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      const index = installPromptWaiters.indexOf(onReady)
      if (index >= 0) {
        installPromptWaiters.splice(index, 1)
      }
      resolve(deferredPrompt !== null)
    }, timeoutMs)

    function onReady() {
      window.clearTimeout(timer)
      resolve(deferredPrompt !== null)
    }

    installPromptWaiters.push(onReady)
  })
}

function matchStandaloneDisplayMode(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return STANDALONE_DISPLAY_MODES.some((mode) =>
    window.matchMedia(`(display-mode: ${mode})`).matches
  )
}

export function isPwaStandalone(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  const nav = window.navigator as Navigator & { standalone?: boolean }
  return matchStandaloneDisplayMode() || nav.standalone === true
}

/**
 * PWA install requires http(s) on a secure context (HTTPS, localhost, or 127.0.0.1).
 * file:// pages must not offer install — Edge on macOS can create a broken shortcut
 * that opens a saved HTML file from Downloads instead of the live site.
 */
export function isInstallablePwaOrigin(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  const protocol = window.location.protocol
  if (protocol !== 'http:' && protocol !== 'https:') {
    return false
  }
  return window.isSecureContext
}

/** iPhone, iPod, iPad, and iPadOS “desktop site” mode (MacIntel + touch). */
export function isIosDevice(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  const ua = navigator.userAgent
  if (/iPhone|iPad|iPod/i.test(ua)) {
    return true
  }
  return navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
}

export function isIosAddToHomeScreenEligible(): boolean {
  if (isPwaStandalone()) {
    return false
  }
  return isIosDevice()
}

function isAndroidDevice(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  return /Android/i.test(navigator.userAgent)
}

function isFirefoxBrowser(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  const ua = navigator.userAgent
  return /Firefox/i.test(ua) && !/Seamonkey/i.test(ua) && !/FxiOS/i.test(ua)
}

function isSafariMacBrowser(): boolean {
  if (typeof navigator === 'undefined' || isIosDevice()) {
    return false
  }
  const ua = navigator.userAgent
  const isSafariEngine =
    /Safari/i.test(ua) &&
    !/Chrome|Chromium|Edg|OPR|OPiOS|CriOS|EdgiOS|FxiOS|SamsungBrowser|Brave/i.test(ua)
  return isSafariEngine && /Macintosh|Mac OS X/i.test(ua)
}

function isChromiumBasedBrowser(): boolean {
  if (typeof navigator === 'undefined' || isIosDevice()) {
    return false
  }
  const ua = navigator.userAgent
  if (isFirefoxBrowser()) {
    return false
  }
  return /Chrome|Chromium|Edg|OPR|SamsungBrowser|Brave|Vivaldi/i.test(ua)
}

/**
 * Best-effort install surface for hint text and UI eligibility.
 * iOS always uses WebKit (Safari, Chrome, Edge, Firefox on iOS).
 */
export function detectPwaInstallSurface(): PwaInstallSurface {
  if (typeof navigator === 'undefined') {
    return 'unknown'
  }
  if (isIosDevice()) {
    return 'ios'
  }
  if (isAndroidDevice()) {
    return 'android'
  }
  if (isFirefoxBrowser()) {
    return 'firefox'
  }
  if (isSafariMacBrowser()) {
    return 'safari-macos'
  }
  if (isChromiumBasedBrowser()) {
    return 'chromium'
  }
  return 'unknown'
}

function isDevWithoutPwa(): boolean {
  if (import.meta.env.MODE === 'test') {
    return false
  }
  return import.meta.env.DEV && import.meta.env.VITE_PWA_DEV !== '1'
}

function surfaceSupportsInstallUi(surface: PwaInstallSurface): boolean {
  if (surface === 'firefox') {
    return false
  }
  if (surface === 'ios' || surface === 'android' || surface === 'chromium' || surface === 'safari-macos') {
    return true
  }
  if (surface === 'unknown' && !computeIsMobileClient()) {
    return true
  }
  return false
}

/**
 * Show install menu when the user can install or should get platform instructions.
 */
export function canShowPwaInstallUi(): boolean {
  if (isPwaStandalone() || sessionInstalled.value) {
    return false
  }
  if (!isInstallablePwaOrigin()) {
    return false
  }
  if (installAvailable.value) {
    return true
  }
  return surfaceSupportsInstallUi(detectPwaInstallSurface())
}

function hintForSurface(surface: PwaInstallSurface): PwaInstallResult {
  switch (surface) {
    case 'ios':
      return 'ios-hint'
    case 'android':
      return 'android-hint'
    case 'safari-macos':
      return 'safari-macos-hint'
    case 'chromium':
    case 'unknown':
      return 'desktop-hint'
    default:
      return 'unavailable'
  }
}

/**
 * Try to open the native install dialog after user click.
 * Waits briefly for beforeinstallprompt when it has not fired yet.
 */
export async function promptPwaInstall(): Promise<PwaInstallResult> {
  if (!isInstallablePwaOrigin()) {
    return 'insecure-hint'
  }

  if (!deferredPrompt) {
    await waitForInstallPrompt(INSTALL_PROMPT_WAIT_MS)
  }

  if (deferredPrompt) {
    await deferredPrompt.prompt()
    const choice = await deferredPrompt.userChoice
    deferredPrompt = null
    installAvailable.value = false
    if (choice.outcome === 'accepted') {
      sessionInstalled.value = true
      return 'installed'
    }
    return 'dismissed'
  }

  if (isDevWithoutPwa()) {
    return 'dev-hint'
  }

  const surface = detectPwaInstallSurface()
  if (!surfaceSupportsInstallUi(surface)) {
    return 'unavailable'
  }

  return hintForSurface(surface)
}

export type PwaInstallFeedback = {
  kind: 'success' | 'info'
  messageKey: string
}

/** Map install prompt result to a toast message key (null = no toast). */
export function getPwaInstallFeedback(result: PwaInstallResult): PwaInstallFeedback | null {
  switch (result) {
    case 'installed':
      return { kind: 'success', messageKey: 'auth.pwaInstallSuccess' }
    case 'ios-hint':
      return { kind: 'info', messageKey: 'auth.pwaIosInstallHint' }
    case 'android-hint':
      return { kind: 'info', messageKey: 'auth.pwaAndroidInstallHint' }
    case 'safari-macos-hint':
      return { kind: 'info', messageKey: 'auth.pwaSafariMacInstallHint' }
    case 'desktop-hint':
      return { kind: 'info', messageKey: 'auth.pwaDesktopInstallHint' }
    case 'dev-hint':
      return { kind: 'info', messageKey: 'auth.pwaDevInstallHint' }
    case 'insecure-hint':
      return { kind: 'info', messageKey: 'auth.pwaInsecureOriginHint' }
    case 'dismissed':
    case 'unavailable':
      return null
    default:
      return null
  }
}
