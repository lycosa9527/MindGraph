import { describe, expect, it } from 'vitest'

import { resolveFloatingToolbarAnchor } from '@/composables/canvasToolbar/useNodeFloatingToolbarPosition'

const CONTAINER = { left: 0, top: 0, right: 1000, bottom: 800 }

describe('resolveFloatingToolbarAnchor', () => {
  it('places the toolbar above when there is room after fit-to-screen', () => {
    const pos = resolveFloatingToolbarAnchor({
      nodeBounds: { left: 400, top: 120, right: 520, bottom: 160 },
      containerBounds: CONTAINER,
      toolbarHeight: 40,
      toolbarWidth: 360,
      gapPx: 10,
      padPx: 8,
    })
    expect(pos.visible).toBe(true)
    expect(pos.placement).toBe('above')
    expect(pos.top).toBe(110)
    expect(pos.left).toBe(460)
  })

  it('flips below when the node sits at the top edge', () => {
    const pos = resolveFloatingToolbarAnchor({
      nodeBounds: { left: 400, top: 12, right: 520, bottom: 52 },
      containerBounds: CONTAINER,
      toolbarHeight: 40,
      toolbarWidth: 360,
      gapPx: 10,
      padPx: 8,
    })
    expect(pos.placement).toBe('below')
    expect(pos.top).toBe(62)
  })

  it('clamps horizontally so a wide bar stays inside the container', () => {
    const pos = resolveFloatingToolbarAnchor({
      nodeBounds: { left: 0, top: 200, right: 40, bottom: 240 },
      containerBounds: CONTAINER,
      toolbarHeight: 40,
      toolbarWidth: 360,
      gapPx: 10,
      padPx: 8,
    })
    // half width 180 + pad 8
    expect(pos.left).toBe(188)
    expect(pos.placement).toBe('above')
  })
})
