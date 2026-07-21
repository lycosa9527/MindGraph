import { describe, expect, it } from 'vitest'

import {
  remapMindMapMeasuredDimensionsAfterReload,
  remapMindMapNodeIdAfterReload,
  remapMindMapNodeIdsAfterReload,
} from '@/stores/diagram/mindMapCollapse'
import { MINDMAP_NODE_UID_DATA_KEY } from '@/utils/mindMapNodeUid'
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

  it('follows mindMapUid when duplicate labels are reparented', () => {
    const oldNodes: DiagramNode[] = [
      { id: 'topic', text: 'Root', type: 'topic' },
      {
        id: 'branch-r-1-0',
        text: '你好',
        type: 'branch',
        data: { [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a' },
      },
      {
        id: 'branch-r-2-1',
        text: '子项A',
        type: 'branch',
        data: { [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a1' },
      },
      {
        id: 'branch-r-1-1',
        text: '你好',
        type: 'branch',
        data: { [MINDMAP_NODE_UID_DATA_KEY]: 'uid-b' },
      },
    ]
    const oldConnections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'branch-r-1-0', target: 'branch-r-2-1' },
      { id: 'c2', source: 'topic', target: 'branch-r-1-1' },
    ]
    // Move first 你好 under the second 你好 — texts collide without uid.
    const newNodes: DiagramNode[] = [
      { id: 'topic', text: 'Root', type: 'topic' },
      {
        id: 'branch-r-1-0',
        text: '你好',
        type: 'branch',
        data: { [MINDMAP_NODE_UID_DATA_KEY]: 'uid-b' },
      },
      {
        id: 'branch-r-2-1',
        text: '你好',
        type: 'branch',
        data: { [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a' },
      },
      {
        id: 'branch-r-3-2',
        text: '子项A',
        type: 'branch',
        data: { [MINDMAP_NODE_UID_DATA_KEY]: 'uid-a1' },
      },
    ]
    const newConnections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'branch-r-1-0', target: 'branch-r-2-1' },
      { id: 'c2', source: 'branch-r-2-1', target: 'branch-r-3-2' },
    ]

    expect(
      remapMindMapNodeIdAfterReload(
        'branch-r-1-0',
        oldNodes,
        oldConnections,
        newNodes,
        newConnections
      )
    ).toBe('branch-r-2-1')
    expect(
      remapMindMapNodeIdAfterReload(
        'branch-r-1-1',
        oldNodes,
        oldConnections,
        newNodes,
        newConnections
      )
    ).toBe('branch-r-1-0')
  })

  it('follows unique own-text when a branch is reparented to a new depth', () => {
    const oldNodes: DiagramNode[] = [
      { id: 'topic', text: 'Root', type: 'topic' },
      { id: 'branch-r-1-0', text: 'A', type: 'branch' },
      { id: 'branch-r-2-1', text: 'A1', type: 'branch' },
      { id: 'branch-r-1-1', text: 'B', type: 'branch' },
    ]
    const oldConnections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'branch-r-1-0', target: 'branch-r-2-1' },
      { id: 'c2', source: 'topic', target: 'branch-r-1-1' },
    ]
    // A moved under B: topic→B→A→A1
    const newNodes: DiagramNode[] = [
      { id: 'topic', text: 'Root', type: 'topic' },
      { id: 'branch-r-1-0', text: 'B', type: 'branch' },
      { id: 'branch-r-2-1', text: 'A', type: 'branch' },
      { id: 'branch-r-3-2', text: 'A1', type: 'branch' },
    ]
    const newConnections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'branch-r-1-0', target: 'branch-r-2-1' },
      { id: 'c2', source: 'branch-r-2-1', target: 'branch-r-3-2' },
    ]

    expect(
      remapMindMapNodeIdAfterReload(
        'branch-r-1-0',
        oldNodes,
        oldConnections,
        newNodes,
        newConnections
      )
    ).toBe('branch-r-2-1')
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

  it('keeps measured sizes across sibling insert and only estimates the new node', () => {
    // Before: A, B. Enter below A → A, New Branch, B (path indices for B shift).
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
      {
        id: 'topic',
        text: 'Root',
        type: 'topic',
        data: { estimatedWidth: 100, estimatedHeight: 40 },
      },
      {
        id: 'branch-r-1-0',
        text: 'A',
        type: 'branch',
        data: { estimatedWidth: 60, estimatedHeight: 28 },
      },
      {
        id: 'branch-r-1-1',
        text: 'New Branch',
        type: 'branch',
        data: { estimatedWidth: 96, estimatedHeight: 28 },
      },
      {
        id: 'branch-r-1-2',
        text: 'B',
        type: 'branch',
        data: { estimatedWidth: 50, estimatedHeight: 28 },
      },
    ]
    const newConnections: Connection[] = [
      { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
      { id: 'c1', source: 'topic', target: 'branch-r-1-1' },
      { id: 'c2', source: 'topic', target: 'branch-r-1-2' },
    ]

    expect(
      remapMindMapNodeIdAfterReload(
        'branch-r-1-1',
        oldNodes,
        oldConnections,
        newNodes,
        newConnections
      )
    ).toBe('branch-r-1-2')

    const remapped = remapMindMapMeasuredDimensionsAfterReload(
      { topic: 180, 'branch-r-1-0': 120, 'branch-r-1-1': 80 },
      { topic: 48, 'branch-r-1-0': 34, 'branch-r-1-1': 34 },
      oldNodes,
      oldConnections,
      newNodes,
      newConnections
    )

    expect(remapped.widths.topic).toBe(180)
    expect(remapped.heights.topic).toBe(48)
    expect(remapped.widths['branch-r-1-0']).toBe(120)
    expect(remapped.heights['branch-r-1-0']).toBe(34)
    expect(remapped.widths['branch-r-1-2']).toBe(80)
    expect(remapped.heights['branch-r-1-2']).toBe(34)
    expect(remapped.widths['branch-r-1-1']).toBe(96)
    expect(remapped.heights['branch-r-1-1']).toBe(28)
  })
})
