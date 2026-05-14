import { describe, expect, it } from 'vitest'

import {
  countLayoutOverlapsByFootprints,
  extractCmapLayoutPositionsByLabel,
} from '@/utils/cmapLayoutExtract'

describe('extractCmapLayoutPositionsByLabel', () => {
  it('returns empty layout when bytes are not a Java serialization stream', () => {
    expect(extractCmapLayoutPositionsByLabel(new Uint8Array([1, 2, 3, 4]))).toEqual({})
  })

  it('overlap oracle counts touching pills that share a row when TL anchors collide', () => {
    const squashed = {
      alphaTopic: { x: 120, y: 120 },
      branchOne: { x: 155, y: 124 },
      branchTwo: { x: 410, y: 430 },
    }
    expect(countLayoutOverlapsByFootprints(squashed, 'alphaTopic')).toBeGreaterThan(0)
  })

  it('overlap oracle yields zero collisions when anchors are spaced for default footprints', () => {
    const spaced = {
      TopicRoot: { x: 180, y: 200 },
      leftNode: { x: 80, y: 320 },

      rightNode: { x: 520, y: 320 },
    }

    expect(countLayoutOverlapsByFootprints(spaced, 'TopicRoot')).toBe(0)
  })
})
