/**
 * Double-bubble topic edges share one handle on each side of the circle.
 */
import { describe, expect, it } from 'vitest'

import { loadDoubleBubbleMapSpec } from '@/stores/specLoader/doubleBubbleMap'

describe('double bubble topic handles', () => {
  it('meets every line on a topic side at one handle', () => {
    const { connections } = loadDoubleBubbleMapSpec({
      left: 'A',
      right: 'B',
      similarities: ['s1', 's2'],
      leftDifferences: ['a1', 'a2', 'a3'],
      rightDifferences: ['b1', 'b2', 'b3'],
    })

    const fromLeft = connections.filter((edge) => edge.source === 'left-topic')
    const fromRight = connections.filter((edge) => edge.source === 'right-topic')
    expect(fromLeft.map((edge) => edge.sourceHandle)).toEqual([
      'right',
      'right',
      'left',
      'left',
      'left',
    ])
    expect(fromRight.map((edge) => edge.sourceHandle)).toEqual([
      'left',
      'left',
      'right',
      'right',
      'right',
    ])
  })
})
