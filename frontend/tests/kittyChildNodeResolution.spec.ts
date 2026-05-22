import { describe, expect, it } from 'vitest'

import {
  buildKittyChildren,
  resolveKittyChildNodeId,
} from '../src/composables/kitty/kittyDiagramChildren'

describe('resolveKittyChildNodeId', () => {
  it('maps child index for mindmap branches, not raw nodes array', () => {
    const nodes = [
      { id: 'topic', type: 'topic', text: 'Root' },
      { id: 'branch-0-0', type: 'branch', text: 'A' },
      { id: 'branch-0-1', type: 'branch', text: 'B' },
    ]
    expect(resolveKittyChildNodeId('mindmap', nodes, { nodeIndex: 0 })).toBe('branch-0-0')
    expect(resolveKittyChildNodeId('mindmap', nodes, { nodeIndex: 1 })).toBe('branch-0-1')
    expect(buildKittyChildren('mindmap', nodes)).toHaveLength(2)
  })

  it('prefers explicit node id', () => {
    const nodes = [{ id: 'context-1', type: 'context', text: 'One' }]
    expect(resolveKittyChildNodeId('circle_map', nodes, { nodeId: 'context-1', nodeIndex: 9 })).toBe(
      'context-1'
    )
  })
})

describe('click wheel detent math', () => {
  it('uses one step per child', () => {
    for (const count of [3, 5, 8, 12]) {
      expect(360 / count).toBeCloseTo(360 / Math.max(count, 1))
    }
  })
})
