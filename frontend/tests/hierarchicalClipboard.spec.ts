import { describe, expect, it } from 'vitest'

import { extractHierarchicalClipboard } from '@/stores/diagram/hierarchicalClipboardExtract'
import type { DiagramData } from '@/types'

function mindMapData(): DiagramData {
  return {
    nodes: [
      { id: 'topic', text: '主题', type: 'topic', position: { x: 0, y: 0 } },
      { id: 'branch-r-1-0', text: '历史', type: 'branch', position: { x: 1, y: 0 } },
      { id: 'branch-r-2-0', text: '唐朝', type: 'branch', position: { x: 2, y: 0 } },
    ],
    connections: [
      { id: 'e1', source: 'topic', target: 'branch-r-1-0' },
      { id: 'e2', source: 'branch-r-1-0', target: 'branch-r-2-0' },
    ],
  }
}

describe('hierarchicalClipboard extract', () => {
  it('extracts mind map branch subtree with children', () => {
    const clip = extractHierarchicalClipboard({
      diagramType: 'mindmap',
      data: mindMapData(),
      nodeIds: ['branch-r-1-0'],
      getMindMapDescendantIds: () => new Set(['branch-r-1-0', 'branch-r-2-0']),
      getTreeMapDescendantIds: () => new Set(),
    })
    expect(clip?.payload.kind).toBe('mindmap_branches')
    if (clip?.payload.kind === 'mindmap_branches') {
      expect(clip.payload.branches[0]?.text).toBe('历史')
      expect(clip.payload.branches[0]?.children?.[0]?.text).toBe('唐朝')
    }
  })

  it('dedupes child selection when parent branch is also selected', () => {
    const clip = extractHierarchicalClipboard({
      diagramType: 'mindmap',
      data: mindMapData(),
      nodeIds: ['branch-r-1-0', 'branch-r-2-0'],
      getMindMapDescendantIds: (root) =>
        root === 'branch-r-1-0'
          ? new Set(['branch-r-1-0', 'branch-r-2-0'])
          : new Set([root]),
      getTreeMapDescendantIds: () => new Set(),
    })
    expect(clip?.payload.kind).toBe('mindmap_branches')
    if (clip?.payload.kind === 'mindmap_branches') {
      expect(clip.payload.branches).toHaveLength(1)
    }
  })
})
