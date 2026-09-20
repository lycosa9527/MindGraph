import { afterEach, describe, expect, it } from 'vitest'

import {
  applyTsecCaptchaToLoginCard,
  clampTsecCaptchaCenter,
  findTsecCaptchaAnchor,
  findTsecCaptchaPopup,
  positionTsecCaptchaOverAnchor,
} from '@/utils/tsec/positionTsecCaptcha'
import {
  TSEC_EMBED_HOST_CLASS,
  TSEC_EMBED_LAYER_CLASS,
  mountTsecCaptchaOnLoginCard,
  placeTsecEmbedLayer,
} from '@/utils/tsec/mountTsecCaptchaHost'

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

  it('shifts the popup from the viewport center onto the login card', () => {
    const anchor = placeBox('auth-page-card', 700, 120, 400, 480)
    const popup = placeBox('tcaptcha-transform', 0, 0, 360, 360)
    expect(findTsecCaptchaPopup()).toBe(popup)
    positionTsecCaptchaOverAnchor(popup, anchor, { innerWidth: 1280, innerHeight: 800 })
    expect(popup.style.transform).toBe('translate(calc(-50% + 260px), calc(-50% + -40px))')
  })

  it('uses the captcha iframe parent when the transform class is missing', () => {
    const wrap = placeBox('tsec-iframe-wrap', 0, 0, 360, 360)
    const iframe = document.createElement('iframe')
    iframe.src = 'https://turing.captcha.qcloud.com/cap_union_new_show'
    wrap.appendChild(iframe)
    expect(findTsecCaptchaPopup()).toBe(wrap)
  })

  it('sizes the embed layer to the login card', () => {
    const card = placeBox('auth-page-card', 640, 80, 400, 520, { 'data-tsec-anchor': '' })
    const layer = placeBox('tsec-layer-probe', 0, 0, 10, 10)
    placeTsecEmbedLayer(layer, card, { innerWidth: 1280, innerHeight: 800 })
    expect(layer.style.left).toBe('640px')
    expect(layer.style.top).toBe('80px')
    expect(layer.style.width).toBe('400px')
    expect(layer.style.height).toBe('520px')
  })

  it('mounts and removes the embed host over the login card', () => {
    placeBox('auth-page-card', 640, 80, 400, 520, { 'data-tsec-anchor': '' })
    const mounted = mountTsecCaptchaOnLoginCard()
    expect(mounted.host.className).toBe(TSEC_EMBED_HOST_CLASS)
    const live = document.querySelector(`.${TSEC_EMBED_LAYER_CLASS}`)
    expect(live).toBeInstanceOf(HTMLElement)
    expect((live as HTMLElement).style.left).toBe('640px')
    mounted.release()
    expect(document.querySelector(`.${TSEC_EMBED_LAYER_CLASS}`)).toBeNull()
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
