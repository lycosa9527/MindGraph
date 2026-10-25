import { describe, expect, it } from 'vitest'

import { diagramFooterChipY, diagramFooterFonts } from '@/utils/diagramFooterBand'

describe('diagramFooterBand', () => {
  it('places the suggestion line under the caption', () => {
    const fonts = diagramFooterFonts('bridge')
    const { labelY, chipsY } = diagramFooterChipY(100, 'bridge')
    expect(labelY).toBe(115)
    expect(chipsY).toBe(115 + fonts.label + 8)
  })
})
