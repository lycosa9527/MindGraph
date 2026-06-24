import { describe, expect, it } from 'vitest'

import { getEdgeTypeForDiagram } from '@/stores/diagram/events'

describe('mind map classic vs v2 separation', () => {
  it('uses curved edges for legacy mind maps', () => {
    expect(getEdgeTypeForDiagram('mind_map', 'legacy')).toBe('curved')
    expect(getEdgeTypeForDiagram('mindmap', 'legacy')).toBe('curved')
  })

  it('uses orthogonal edges for v2 mind maps', () => {
    expect(getEdgeTypeForDiagram('mind_map', 'v2')).toBe('mindmapOrthogonal')
    expect(getEdgeTypeForDiagram('mindmap', 'v2')).toBe('mindmapOrthogonal')
  })
})
