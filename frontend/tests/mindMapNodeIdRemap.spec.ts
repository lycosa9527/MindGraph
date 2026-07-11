import { describe, expect, it } from 'vitest'

import {
  remapMindMapNodeIdAfterReload,
  remapMindMapNodeIdsAfterReload,
} from '@/stores/diagram/mindMapCollapse'
import type { Connection, DiagramNode } from '@/types'

describe('remapMindMapNodeIdAfterReload', () => {
  it('keeps selection on a later sibling when an earlier branch gains children', () => {
    // Before: A=r-1-0, B=r-1-1 (selected). After paste under A: B becomes r-1-3.
    const oldNodes: DiagramNode[] = [
      { id: 'topic', text: 'Root', type: 'topic' },
      { id: 'branch-r-1-0', text: 'A', type: 'branch' },
      { id: 'branch-r-1-1', text: 'B', type: 'branch' },
    ]
    const oldConnections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-r-1-1' },
    ]
    const newNodes: DiagramNode[] = [
      { id: 'topic', text: 'Root', type: 'topic' },
      { id: 'branch-r-1-0', text: 'A', type: 'branch' },
      { id: 'branch-r-2-1', text: 'A1', type: 'branch' },
      { id: 'branch-r-2-2', text: 'A2', type: 'branch' },
      { id: 'branch-r-1-3', text: 'B', type: 'branch' },
    ]
    const newConnections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'branch-r-1-0', target: 'branch-r-2-1' },
      { id: 'c2', source: 'branch-r-1-0', target: 'branch-r-2-2' },
      { id: 'c3', source: 'topic', target: 'branch-r-1-3' },
    ]

    expect(
      remapMindMapNodeIdAfterReload(
        'branch-r-1-1',
        oldNodes,
        oldConnections,
        newNodes,
        newConnections
      )
    ).toBe('branch-r-1-3')

    expect(
      remapMindMapNodeIdsAfterReload(
        ['branch-r-1-1'],
        oldNodes,
        oldConnections,
        newNodes,
        newConnections
      )
    ).toEqual(['branch-r-1-3'])
  })

  it('follows text path when clockwise redistribute moves a branch to the other side', () => {
    const oldNodes: DiagramNode[] = [
      { id: 'topic', text: 'Root', type: 'topic' },
      { id: 'branch-r-1-0', text: 'Keep', type: 'branch' },
      { id: 'branch-r-1-1', text: 'Moved', type: 'branch' },
    ]
    const oldConnections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-r-1-1' },
    ]
    const newNodes: DiagramNode[] = [
      { id: 'topic', text: 'Root', type: 'topic' },
      { id: 'branch-r-1-0', text: 'Keep', type: 'branch' },
      { id: 'branch-l-1-0', text: 'Moved', type: 'branch' },
    ]
    const newConnections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-l-1-0' },
    ]

    expect(
      remapMindMapNodeIdAfterReload(
        'branch-r-1-1',
        oldNodes,
        oldConnections,
        newNodes,
        newConnections
      )
    ).toBe('branch-l-1-0')
  })
})
