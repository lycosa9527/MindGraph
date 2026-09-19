import { afterEach, describe, expect, it } from 'vitest'

import {
  applyTsecCaptchaToLoginCard,
  clampTsecCaptchaCenter,
  findTsecCaptchaAnchor,
  findTsecCaptchaPopup,
  positionTsecCaptchaOverAnchor,
} from '@/utils/tsec/positionTsecCaptcha'

function placeBox(
  className: string,
  left: number,
  top: number,
  width: number,
  height: number,
  extra?: Record<string, string>
): HTMLElement {
  const el = document.createElement('div')
  el.className = className
  if (extra) {
    Object.entries(extra).forEach(([key, value]) => {
      el.setAttribute(key, value)
    })
  }
  Object.defineProperty(el, 'offsetWidth', { configurable: true, value: width })
  Object.defineProperty(el, 'offsetHeight', { configurable: true, value: height })
  el.getBoundingClientRect = () =>
    ({
      left,
      top,
      width,
      height,
      right: left + width,
      bottom: top + height,
      x: left,
      y: top,
      toJSON: () => ({}),
    }) as DOMRect
  document.body.appendChild(el)
  return el
}

describe('positionTsecCaptcha', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('prefers the /auth login card as the slider anchor', () => {
    placeBox('swiss-glass-card', 0, 0, 320, 400)
    placeBox('swiss-glass-card--auth', 20, 20, 320, 400)
    const card = placeBox('auth-page-card', 640, 80, 400, 520, { 'data-tsec-anchor': '' })
    expect(findTsecCaptchaAnchor()).toBe(card)
  })

  it('centers the popup on the login card and keeps it on screen', () => {
    const anchor = placeBox('auth-page-card', 700, 120, 400, 480)
    const popup = placeBox('tcaptcha-transform', 0, 0, 360, 360)
    expect(findTsecCaptchaPopup()).toBe(popup)
    positionTsecCaptchaOverAnchor(popup, anchor, { innerWidth: 1280, innerHeight: 800 })
    expect(popup.style.left).toBe('900px')
    expect(popup.style.top).toBe('360px')
    expect(popup.style.position).toBe('fixed')
  })

  it('clamps a card that sits near the viewport edge', () => {
    const center = clampTsecCaptchaCenter(40, 40, 360, 360, 390, 700)
    expect(center.x).toBe(192)
    expect(center.y).toBe(192)
  })

  it('no-ops until both the card and the Tencent popup exist', () => {
    expect(applyTsecCaptchaToLoginCard()).toBe(false)
    placeBox('auth-page-card', 100, 80, 360, 400)
    expect(applyTsecCaptchaToLoginCard()).toBe(false)
    placeBox('tcaptcha-transform', 0, 0, 360, 360)
    expect(applyTsecCaptchaToLoginCard()).toBe(true)
  })
})
