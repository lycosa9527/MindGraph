/**
 * HarmonyOS NEXT, from the ArkWeb User-Agent guide.
 * The OS marker is OpenHarmony. A phone is DeviceType "Phone"
 * (DeviceCompat "Mobile"). Tablet and PC are not phones, so a wide
 * inner screen still uses the touch shell only for phones.
 */

const HARMONY_OS_UA = /OpenHarmony/i
const ARKWEB_KERNEL_UA = /OpenHarmony|ArkWeb|HarmonyOS|HuaweiBrowser/i
const HARMONY_PHONE_DEVICE_UA = /\(Phone;/i
const HARMONY_NON_PHONE_DEVICE_UA = /\((?:Tablet|PC);/i
const HARMONY_MOBILE_COMPAT_UA = /(?:^|\s)Mobile(?:\s|$)/

export function isArkWebUserAgent(userAgent: string): boolean {
  return ARKWEB_KERNEL_UA.test(userAgent)
}

export function isHarmonyOsPhoneUserAgent(userAgent: string): boolean {
  if (!HARMONY_OS_UA.test(userAgent)) return false
  if (HARMONY_NON_PHONE_DEVICE_UA.test(userAgent)) return false
  return HARMONY_PHONE_DEVICE_UA.test(userAgent) || HARMONY_MOBILE_COMPAT_UA.test(userAgent)
}

export type VisualViewportBox = {
  width: number
  height: number
  offsetTop: number
  offsetLeft: number
}

/** Ignore a 0 box reported mid-fold. Returns null when the size is unusable. */
export function readVisualViewportBox(
  view: Pick<VisualViewport, 'width' | 'height' | 'offsetTop' | 'offsetLeft'> | null,
  fallback: { width: number; height: number }
): VisualViewportBox | null {
  const width = view?.width ?? fallback.width
  const height = view?.height ?? fallback.height
  if (!(width > 1) || !(height > 1)) return null
  return {
    width,
    height,
    offsetTop: view?.offsetTop ?? 0,
    offsetLeft: view?.offsetLeft ?? 0,
  }
}

export function installArkWebDocumentClass(userAgent?: string): void {
  if (typeof document === 'undefined') return
  const ua = userAgent ?? (typeof navigator !== 'undefined' ? navigator.userAgent : '')
  if (!isArkWebUserAgent(ua)) return
  document.documentElement.classList.add('mg-arkweb')
}

/** Keep dialogs and the canvas shell on the visible window across a fold. */
export function installVisualViewportCssVars(): void {
  if (typeof window === 'undefined' || typeof document === 'undefined') return
  let frame = 0
  let previous = ''

  const apply = (): void => {
    frame = 0
    const box = readVisualViewportBox(window.visualViewport, {
      width: window.innerWidth,
      height: window.innerHeight,
    })
    if (!box) return
    const next = `${box.width}|${box.height}|${box.offsetTop}|${box.offsetLeft}`
    if (next === previous) return
    previous = next
    const root = document.documentElement
    root.style.setProperty('--mg-vvw', `${Math.round(box.width)}px`)
    root.style.setProperty('--mg-vvh', `${Math.round(box.height)}px`)
    root.style.setProperty('--mg-vv-top', `${Math.round(box.offsetTop)}px`)
    root.style.setProperty('--mg-vv-left', `${Math.round(box.offsetLeft)}px`)
  }

  const schedule = (): void => {
    if (frame !== 0) return
    frame = window.requestAnimationFrame(apply)
  }

  apply()
  window.visualViewport?.addEventListener('resize', schedule)
  window.visualViewport?.addEventListener('scroll', schedule)
  window.addEventListener('resize', schedule)
  window.addEventListener('orientationchange', schedule)
}
