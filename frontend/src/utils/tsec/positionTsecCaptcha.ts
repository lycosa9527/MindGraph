/**
 * Pin Tencent Captcha 2.0's popup to the login card.
 *
 * Popup mode is viewport-centered (`left/top: 50%`). On `/auth` the card sits on
 * the right (desktop) or under the hero copy (mobile), so the slider must be
 * moved onto that card. Official docs only allow restyling `.tcaptcha-transform`.
 */

export const TSEC_CAPTCHA_POPUP_SELECTOR = '.tcaptcha-transform'
const TSEC_VIEWPORT_PAD_PX = 12
const TSEC_DEFAULT_POPUP_PX = 360

export function findTsecCaptchaPopup(
  root: ParentNode = document
): HTMLElement | null {
  const nodes = root.querySelectorAll<HTMLElement>(TSEC_CAPTCHA_POPUP_SELECTOR)
  if (nodes.length === 0) {
    return null
  }
  return nodes[nodes.length - 1]
}

export function findTsecCaptchaAnchor(
  root: ParentNode = document
): HTMLElement | null {
  return (
    root.querySelector<HTMLElement>('[data-tsec-anchor]') ||
    root.querySelector<HTMLElement>('.auth-page-card') ||
    root.querySelector<HTMLElement>('.swiss-glass-card--auth') ||
    root.querySelector<HTMLElement>('.swiss-glass-card')
  )
}

export function clampTsecCaptchaCenter(
  centerX: number,
  centerY: number,
  popupWidth: number,
  popupHeight: number,
  viewportWidth: number,
  viewportHeight: number,
  pad: number = TSEC_VIEWPORT_PAD_PX
): { x: number; y: number } {
  const halfW = popupWidth / 2
  const halfH = popupHeight / 2
  const minX = pad + halfW
  const maxX = viewportWidth - pad - halfW
  const minY = pad + halfH
  const maxY = viewportHeight - pad - halfH
  return {
    x: Math.min(Math.max(centerX, minX), Math.max(minX, maxX)),
    y: Math.min(Math.max(centerY, minY), Math.max(minY, maxY)),
  }
}

export function positionTsecCaptchaOverAnchor(
  popup: HTMLElement,
  anchor: HTMLElement,
  viewport: Pick<Window, 'innerWidth' | 'innerHeight'> = window
): void {
  const rect = anchor.getBoundingClientRect()
  const popupWidth = popup.offsetWidth || TSEC_DEFAULT_POPUP_PX
  const popupHeight = popup.offsetHeight || TSEC_DEFAULT_POPUP_PX
  const center = clampTsecCaptchaCenter(
    rect.left + rect.width / 2,
    rect.top + rect.height / 2,
    popupWidth,
    popupHeight,
    viewport.innerWidth,
    viewport.innerHeight
  )
  const left = `${center.x}px`
  const top = `${center.y}px`
  if (
    popup.style.position === 'fixed' &&
    popup.style.left === left &&
    popup.style.top === top
  ) {
    return
  }
  popup.style.setProperty('position', 'fixed', 'important')
  popup.style.setProperty('left', left, 'important')
  popup.style.setProperty('top', top, 'important')
  popup.style.setProperty('right', 'auto', 'important')
  popup.style.setProperty('bottom', 'auto', 'important')
  popup.style.setProperty('margin', '0', 'important')
}

export function applyTsecCaptchaToLoginCard(): boolean {
  const anchor = findTsecCaptchaAnchor()
  const popup = findTsecCaptchaPopup()
  if (!anchor || !popup) {
    return false
  }
  positionTsecCaptchaOverAnchor(popup, anchor)
  return true
}

export function bindTsecCaptchaToLoginCard(): () => void {
  let raf = 0
  let tries = 0
  let trackedPopup: HTMLElement | null = null
  let popupObserver: MutationObserver | null = null

  const watchPopup = (popup: HTMLElement): void => {
    if (popup === trackedPopup) {
      return
    }
    popupObserver?.disconnect()
    trackedPopup = popup
    popupObserver = new MutationObserver(onRelayout)
    popupObserver.observe(popup, { attributes: true, attributeFilter: ['style', 'class'] })
  }

  const apply = (): void => {
    applyTsecCaptchaToLoginCard()
    const popup = findTsecCaptchaPopup()
    if (popup) {
      watchPopup(popup)
      return
    }
    if (tries >= 40) {
      return
    }
    tries += 1
    raf = window.requestAnimationFrame(apply)
  }

  const onRelayout = (): void => {
    applyTsecCaptchaToLoginCard()
    const popup = findTsecCaptchaPopup()
    if (popup) {
      watchPopup(popup)
    }
  }

  const treeObserver = new MutationObserver(onRelayout)
  treeObserver.observe(document.body, { childList: true, subtree: true })
  window.addEventListener('resize', onRelayout)
  window.addEventListener('scroll', onRelayout, true)
  apply()

  return () => {
    treeObserver.disconnect()
    popupObserver?.disconnect()
    window.removeEventListener('resize', onRelayout)
    window.removeEventListener('scroll', onRelayout, true)
    window.cancelAnimationFrame(raf)
  }
}
