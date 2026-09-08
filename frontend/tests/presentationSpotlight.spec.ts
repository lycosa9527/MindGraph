import { describe, expect, it } from 'vitest'

import {
  presentationRectSpotlightStyle,
  presentationSpotlightBackground,
  presentationSpotlightHoleSize,
  presentationSpotlightVisualScale,
} from '@/config/presentationSpotlight'

describe('presentationSpotlight', () => {
  it('builds the same soft hole as the canvas presentation tool', () => {
    expect(presentationSpotlightBackground(120, 80, 1)).toBe(
      'radial-gradient(circle at 120px 80px, transparent 0%, transparent 150px, rgba(0,0,0,0.62) 195px)'
    )
    expect(presentationSpotlightVisualScale(1, 900, 560)).toBe(1)
    expect(presentationSpotlightVisualScale(1, 160, 100)).toBeCloseTo(100 / 720)
  })

  it('builds a soft rectangular hole from the same dim and feather', () => {
    expect(presentationSpotlightHoleSize(1, 'rect')).toEqual({ halfW: 190, halfH: 120 })
    const style = presentationRectSpotlightStyle(200, 100, 1)
    expect(style.background).toBe('rgba(0,0,0,0.62)')
    expect(style.maskImage).toContain('linear-gradient(to right')
    expect(style.maskImage).toContain('linear-gradient(to bottom')
  })
})
