import { describe, expect, it } from 'vitest'

import {
  AUTH_LOGIN_HERO_BLOCKING_OVERLAY_SELECTOR,
  authLoginHeroNativeVideoLayerRisk,
  documentHasAuthLoginHeroBlockingOverlay,
  isAuthLoginHeroBlockingOverlayElement,
} from '@/utils/authLoginHeroVideoLayer'

describe('authLoginHeroVideoLayer', () => {
  it('lists teleported overlay roots that must cover the cinema clip', () => {
    expect(AUTH_LOGIN_HERO_BLOCKING_OVERLAY_SELECTOR).toContain('.swm-overlay')
    expect(AUTH_LOGIN_HERO_BLOCKING_OVERLAY_SELECTOR).toContain(
      '.swiss-glass-card-overlay:not(.swiss-glass-card-overlay--auth-split)'
    )
  })

  it('treats Android as native video layer risk', () => {
    expect(
      authLoginHeroNativeVideoLayerRisk(
        'Mozilla/5.0 (Linux; Android 14; HONOR Pad) AppleWebKit/537.36'
      )
    ).toBe(true)
    expect(
      authLoginHeroNativeVideoLayerRisk(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      )
    ).toBe(false)
  })

  it('ignores inline /auth login chrome and hidden overlays', () => {
    const doc = document.implementation.createHTMLDocument('')
    const split = doc.createElement('div')
    split.className = 'swiss-glass-card-overlay swiss-glass-card-overlay--auth-split'
    doc.body.appendChild(split)
    expect(documentHasAuthLoginHeroBlockingOverlay(doc)).toBe(false)

    const hidden = doc.createElement('div')
    hidden.className = 'swm-overlay'
    hidden.style.display = 'none'
    doc.body.appendChild(hidden)
    expect(documentHasAuthLoginHeroBlockingOverlay(doc)).toBe(false)

    const modal = doc.createElement('div')
    modal.className = 'swm-overlay'
    doc.body.appendChild(modal)
    expect(documentHasAuthLoginHeroBlockingOverlay(doc)).toBe(true)
    expect(isAuthLoginHeroBlockingOverlayElement(modal)).toBe(true)
  })
})
