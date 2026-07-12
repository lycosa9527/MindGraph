import { describe, expect, it } from 'vitest'

import {
  buildKittyChildren,
  buildKittyClickWheelNodes,
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
    expect(
      resolveKittyChildNodeId('circle_map', nodes, { nodeId: 'context-1', nodeIndex: 9 })
    ).toBe('context-1')
  })
})

describe('buildKittyClickWheelNodes', () => {
  it('walks mindmap as branch then children (pre-order DFS)', () => {
    const nodes = [
      { id: 'topic', type: 'topic', text: 'Root' },
      { id: 'branch-r-1-0', type: 'branch', text: 'Branch 1' },
      { id: 'branch-r-2-0', type: 'branch', text: 'Child 1a' },
      { id: 'branch-r-2-1', type: 'branch', text: 'Child 1b' },
      { id: 'branch-r-1-1', type: 'branch', text: 'Branch 2' },
      { id: 'branch-r-2-2', type: 'branch', text: 'Child 2a' },
    ]
    const connections = [
      { id: 'c1', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c2', source: 'branch-r-1-0', target: 'branch-r-2-0' },
      { id: 'c3', source: 'branch-r-1-0', target: 'branch-r-2-1' },
      { id: 'c4', source: 'topic', target: 'branch-r-1-1' },
      { id: 'c5', source: 'branch-r-1-1', target: 'branch-r-2-2' },
    ]
    expect(buildKittyClickWheelNodes('mindmap', nodes, connections).map((n) => n.id)).toEqual([
      'branch-r-1-0',
      'branch-r-2-0',
      'branch-r-2-1',
      'branch-r-1-1',
      'branch-r-2-2',
    ])
  })

  it('falls back to flat children when there are no connections', () => {
    const nodes = [
      { id: 'topic', type: 'topic', text: 'Root' },
      { id: 'branch-r-1-0', type: 'branch', text: 'A' },
      { id: 'branch-r-1-1', type: 'branch', text: 'B' },
    ]
    expect(buildKittyClickWheelNodes('mindmap', nodes, [])).toEqual(
      buildKittyChildren('mindmap', nodes)
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
