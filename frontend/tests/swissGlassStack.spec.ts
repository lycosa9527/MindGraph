import { describe, expect, it } from 'vitest'

import {
  SWISS_GLASS_CARD_DIALOG_Z,
  glassCardDialogZIndex,
  glassCardHoldsPopupLayer,
  pushFullScreenGlassCard,
} from '@/components/common/swissGlassStack'

describe('swissGlassStack', () => {
  it('treats only a body-level card as the popup layer', () => {
    expect(
      glassCardHoldsPopupLayer({
        hostIsBody: true,
        teleportDisabled: false,
        overlayClass: '',
      })
    ).toBe(true)
    expect(
      glassCardHoldsPopupLayer({
        hostIsBody: true,
        teleportDisabled: true,
        overlayClass: 'swiss-glass-card-overlay--auth-split',
      })
    ).toBe(false)
    expect(
      glassCardHoldsPopupLayer({
        hostIsBody: false,
        teleportDisabled: false,
        overlayClass: 'swiss-glass-card-overlay--contained',
      })
    ).toBe(false)
  })

  it('lifts confirm and prompt only while a full-screen card is open', () => {
    expect(glassCardDialogZIndex(true)).toBeUndefined()
    const release = pushFullScreenGlassCard()
    try {
      expect(glassCardDialogZIndex(false)).toBeUndefined()
      expect(glassCardDialogZIndex(true)).toBe(SWISS_GLASS_CARD_DIALOG_Z)
      release()
      expect(glassCardDialogZIndex(true)).toBeUndefined()
    } finally {
      release()
    }
  })
})
