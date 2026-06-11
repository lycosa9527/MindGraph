/**
 * PWA install helpers — beforeinstallprompt capture and install UI eligibility.
 */
import { readonly, ref } from 'vue'

import { computeIsMobileClient, isTouchDeviceUserAgent } from '@/utils/isMobileClient'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

const INSTALL_PROMPT_WAIT_MS = 1500

const installAvailable = ref(false)
let deferredPrompt: BeforeInstallPromptEvent | null = null
let listenersBound = false
const installPromptWaiters: Array<() => void> = []

export const pwaInstallAvailable = readonly(installAvailable)

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

export function bindPwaInstallListeners(): void {
  if (listenersBound || typeof window === 'undefined') {
    return
  }
  listenersBound = true

  window.addEventListener('beforeinstallprompt', captureInstallPrompt)

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null
    installAvailable.value = false
  })
}

function waitForInstallPrompt(timeoutMs: number): Promise<boolean> {
  if (deferredPrompt) {
    return Promise.resolve(true)
  }
  if (typeof window === 'undefined') {
    return Promise.resolve(false)
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

export function isPwaStandalone(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  const nav = window.navigator as Navigator & { standalone?: boolean }
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: window-controls-overlay)').matches ||
    nav.standalone === true
  )
}

export function isIosAddToHomeScreenEligible(): boolean {
  if (typeof navigator === 'undefined' || isPwaStandalone()) {
    return false
  }
  const ua = navigator.userAgent
  return /iPhone|iPad|iPod/i.test(ua)
}

function isPhoneUserAgent(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  const ua = navigator.userAgent
  if (/iPhone|iPod|Windows Phone/i.test(ua)) {
    return true
  }
  return /Android.*Mobile/i.test(ua)
}

function isIpadOsDesktopBrowser(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  return navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
}

function isAndroidBrowser(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  return /Android/i.test(navigator.userAgent)
}

function isChromiumBrowser(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  const ua = navigator.userAgent
  return /Chrome|Chromium|Edg|OPR/i.test(ua) && !/iPhone|iPad|iPod/i.test(ua)
}

/**
 * Show install menu when the user can install or should get platform instructions.
 */
export function canShowPwaInstallUi(): boolean {
  if (isPwaStandalone()) {
    return false
  }
  if (installAvailable.value) {
    return true
  }
  if (isIosAddToHomeScreenEligible()) {
    return true
  }
  if (isAndroidBrowser()) {
    return true
  }
  if (isPhoneUserAgent()) {
    return false
  }
  if (isIpadOsDesktopBrowser()) {
    return false
  }
  if (computeIsMobileClient()) {
    return false
  }
  return true
}

export type PwaInstallResult =
  | 'installed'
  | 'dismissed'
  | 'unavailable'
  | 'ios-hint'
  | 'desktop-hint'
  | 'dev-hint'

function isDevWithoutPwa(): boolean {
  return import.meta.env.DEV && import.meta.env.VITE_PWA_DEV !== '1'
}

/**
 * Try to open the native install dialog after user click.
 * Waits briefly for beforeinstallprompt when it has not fired yet.
 */
export async function promptPwaInstall(): Promise<PwaInstallResult> {
  if (!deferredPrompt) {
    await waitForInstallPrompt(INSTALL_PROMPT_WAIT_MS)
  }

  if (deferredPrompt) {
    await deferredPrompt.prompt()
    const choice = await deferredPrompt.userChoice
    deferredPrompt = null
    installAvailable.value = false
    return choice.outcome === 'accepted' ? 'installed' : 'dismissed'
  }

  if (isIosAddToHomeScreenEligible()) {
    return 'ios-hint'
  }
  if (isDevWithoutPwa()) {
    return 'dev-hint'
  }
  if (canShowPwaInstallUi() && isChromiumBrowser()) {
    return 'desktop-hint'
  }
  if (canShowPwaInstallUi()) {
    return 'desktop-hint'
  }
  return 'unavailable'
}
