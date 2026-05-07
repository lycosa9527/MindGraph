import { describe, expect, it } from 'vitest'

import { extractCmapLayoutPositionsByLabel } from '@/utils/cmapLayoutExtract'

describe('extractCmapLayoutPositionsByLabel', () => {
  it('returns empty layout when bytes are not a Java serialization stream', () => {
    expect(extractCmapLayoutPositionsByLabel(new Uint8Array([1, 2, 3, 4]))).toEqual({})
  })
})
