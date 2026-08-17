import { describe, expect, it } from 'vitest'

import { resolveNodeExplainBubbleAnchor } from '@/composables/canvasToolbar/useNodeExplainBubblePosition'

const CONTAINER = { left: 0, top: 0, right: 1000, bottom: 800 }

describe('resolveNodeExplainBubbleAnchor', () => {
  it('places the bubble to the right when the node sits on the left half', () => {
    const pos = resolveNodeExplainBubbleAnchor({
      nodeBounds: { left: 80, top: 300, right: 200, bottom: 360 },
      containerBounds: CONTAINER,
      bubbleWidth: 260,
      bubbleHeight: 110,
      gapPx: 14,
      padPx: 8,
    })
    expect(pos.visible).toBe(true)
    expect(pos.placement).toBe('right')
    expect(pos.left).toBe(214)
    expect(pos.top).toBe(330)
  })

  it('places the bubble to the left when the node sits on the right half', () => {
    const pos = resolveNodeExplainBubbleAnchor({
      nodeBounds: { left: 780, top: 300, right: 920, bottom: 360 },
      containerBounds: CONTAINER,
      bubbleWidth: 260,
      bubbleHeight: 110,
      gapPx: 14,
      padPx: 8,
    })
    expect(pos.placement).toBe('left')
    expect(pos.left).toBe(766)
    expect(pos.top).toBe(330)
  })

  it('flips below when the node sits at the top edge with no side room', () => {
    const pos = resolveNodeExplainBubbleAnchor({
      nodeBounds: { left: 20, top: 10, right: 980, bottom: 70 },
      containerBounds: CONTAINER,
      bubbleWidth: 260,
      bubbleHeight: 110,
      gapPx: 14,
      padPx: 8,
    })
    expect(pos.placement).toBe('below')
    expect(pos.top).toBe(84)
  })
})
