import { describe, expect, it } from 'vitest'

import { besideFitScale } from '@/i18n/besideFitScale'

describe('besideFitScale', () => {
  it('keeps full size when the line fits', () => {
    expect(besideFitScale(280, 180, 1)).toBe(1)
  })

  it('shrinks a line that is wider than the card', () => {
    expect(besideFitScale(200, 400, 1)).toBeCloseTo(0.5)
  })

  it('recovers the unscaled width when the line is already shrunk', () => {
    expect(besideFitScale(200, 200, 0.5)).toBeCloseTo(0.5)
  })

  it('does not shrink below a readable floor', () => {
    expect(besideFitScale(40, 1000, 1)).toBe(0.42)
  })

  it('ignores a missing measurement', () => {
    expect(besideFitScale(0, 100, 1)).toBe(1)
    expect(besideFitScale(100, 0, 1)).toBe(1)
  })
})
