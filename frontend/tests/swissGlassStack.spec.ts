import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import {
  CANVAS_NODE_CHROME_Z,
  MM_ABOVE_NODE_CHROME_CLASS,
  SWISS_GLASS_CANVAS_DIALOG_Z,
  SWISS_GLASS_CARD_DIALOG_Z,
  canvasCoveringOverlayOpen,
  glassCardDialogZIndex,
  glassCardHoldsPopupLayer,
  pushCanvasCoveringOverlay,
  pushFullScreenGlassCard,
} from '@/components/common/swissGlassStack'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

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

  it('keeps canvas dialogs above the selected-node toolbar including !important poppers', () => {
    expect(CANVAS_NODE_CHROME_Z.FLOATING_TOOLBAR_POPPER).toBeGreaterThan(
      CANVAS_NODE_CHROME_Z.FLOATING_TOOLBAR
    )
    expect(SWISS_GLASS_CANVAS_DIALOG_Z).toBeGreaterThan(
      CANVAS_NODE_CHROME_Z.FLOATING_TOOLBAR_POPPER
    )
    expect(SWISS_GLASS_CANVAS_DIALOG_Z).toBeLessThan(10000)
    const css = readFileSync(resolve(root, 'src/styles/swissGlassControls.css'), 'utf8')
    expect(css).toContain(`.el-overlay:has(.${MM_ABOVE_NODE_CHROME_CLASS})`)
    expect(css).toContain('.mm-canvas-center-modal')
    expect(css).not.toContain('.model-sheet-overlay {')
    expect(css).toContain(`z-index: ${SWISS_GLASS_CANVAS_DIALOG_Z} !important`)
    const rail = readFileSync(resolve(root, 'src/styles/mind-map-side-rail-panel.css'), 'utf8')
    expect(rail).toContain(`z-index: ${SWISS_GLASS_CANVAS_DIALOG_Z}`)
    const mobile = readFileSync(
      resolve(root, 'src/pages/mobile/mobileCanvasPage.global.css'),
      'utf8'
    )
    expect(mobile).toMatch(/\.model-sheet-overlay\s*\{[^}]*z-index:\s*2000/)
  })

  it('tracks body dialogs that must hide teleported node chrome', () => {
    expect(canvasCoveringOverlayOpen()).toBe(false)
    const release = pushCanvasCoveringOverlay()
    try {
      expect(canvasCoveringOverlayOpen()).toBe(true)
      const inner = pushCanvasCoveringOverlay()
      inner()
      expect(canvasCoveringOverlayOpen()).toBe(true)
      release()
      expect(canvasCoveringOverlayOpen()).toBe(false)
    } finally {
      release()
    }
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
