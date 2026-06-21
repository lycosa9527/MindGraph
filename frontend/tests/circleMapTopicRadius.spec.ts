import { describe, expect, it } from 'vitest'

import { calculateCircleMapLayout } from '@/stores/specLoader/utils'

describe('circle map default topic radius', () => {
  it('uses text-based floor for short default labels without DOM overrides', () => {
    const layout = calculateCircleMapLayout(8, ['Context 1', 'Context 2'], 'Topic')
    expect(layout.topicR).toBe(60)
  })

  it('does not grow topic when DOM override matches short plain text', () => {
    const layout = calculateCircleMapLayout(8, ['Context 1'], 'Topic', {
      topicR: 45,
    })
    expect(layout.topicR).toBe(60)
  })
})
