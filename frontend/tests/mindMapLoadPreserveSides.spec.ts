import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { loadSpecForDiagramType } from '@/stores/specLoader'
import {
  distributeBranchesClockwise,
  loadMindMapSpec,
  mindMapBranchesClockwiseOrder,
  nodesAndConnectionsToMindMapSpec,
  rebalanceMindMapBranchesIfLeftOnly,
} from '@/stores/specLoader/mindMap'
import { useUIStore } from '@/stores/ui'

function topicChildBranchTexts(
  nodes: { id: string; text?: string }[],
  connections: { source: string; target: string }[],
  side: 'l' | 'r'
): string[] {
  const prefix = side === 'l' ? 'branch-l-' : 'branch-r-'
  const childIds = connections
    .filter((c) => c.source === 'topic' && c.target.startsWith(prefix))
    .map((c) => c.target)
  const byId = new Map(nodes.map((n) => [n.id, n.text ?? '']))
  return childIds
    .slice()
    .sort((a, b) => {
      const aIdx = parseInt(a.split('-')[3] ?? '0', 10)
      const bIdx = parseInt(b.split('-')[3] ?? '0', 10)
      return aIdx - bIdx
    })
    .map((id) => byId.get(id) ?? '')
}

describe('mindmap load preserves left/right sides', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      length: 0,
      key: vi.fn(() => null),
    })
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    useUIStore().mindMapCanvasMode = 'legacy'
  })

  it('round-trips saved nodes/connections without reshuffling branches', () => {
    const initial = loadMindMapSpec({
      topic: '中心主题',
      children: [
        { text: '分支1', children: [{ text: '子项1.1' }, { text: '子项1.2' }] },
        { text: '分支2', children: [{ text: '子项2.1' }, { text: '子项2.2' }] },
        { text: '分支3', children: [{ text: '子项3.1' }, { text: '子项3.2' }] },
        { text: '分支4', children: [{ text: '子项4.1' }, { text: '子项4.2' }] },
      ],
    })

    const rightBefore = topicChildBranchTexts(initial.nodes, initial.connections, 'r')
    const leftBefore = topicChildBranchTexts(initial.nodes, initial.connections, 'l')

    // Simulate first autosave URL sync / library reload of saved generic format.
    const reloaded = loadSpecForDiagramType(
      {
        nodes: initial.nodes,
        connections: initial.connections,
      },
      'mindmap'
    )

    expect(topicChildBranchTexts(reloaded.nodes, reloaded.connections, 'r')).toEqual(rightBefore)
    expect(topicChildBranchTexts(reloaded.nodes, reloaded.connections, 'l')).toEqual(leftBefore)
  })

  it('documents why [...left, ...right] redistribute is not idempotent', () => {
    const initial = loadMindMapSpec({
      topic: '中心主题',
      children: [{ text: '分支1' }, { text: '分支2' }, { text: '分支3' }, { text: '分支4' }],
    })
    const extracted = nodesAndConnectionsToMindMapSpec(initial.nodes, initial.connections)
    const buggy = distributeBranchesClockwise([
      ...extracted.leftBranches,
      ...extracted.rightBranches,
    ])

    expect(buggy.rightBranches.map((b) => b.text)).not.toEqual(
      extracted.rightBranches.map((b) => b.text)
    )
    expect(buggy.leftBranches.map((b) => b.text)).not.toEqual(
      extracted.leftBranches.map((b) => b.text)
    )
  })

  it('rebalances left-only maps after all right branches are removed', () => {
    const initial = loadMindMapSpec({
      topic: 'Topic',
      children: [
        { text: 'R1' },
        { text: 'R2' },
        { text: 'L1' },
        { text: 'L2' },
      ],
    })
    const extracted = nodesAndConnectionsToMindMapSpec(initial.nodes, initial.connections)
    expect(extracted.rightBranches.map((b) => b.text)).toEqual(['R1', 'R2'])
    expect(extracted.leftBranches.map((b) => b.text)).toEqual(['L2', 'L1'])

    const afterDeleteRight = rebalanceMindMapBranchesIfLeftOnly(extracted.leftBranches, [])
    expect(afterDeleteRight.redistributed).toBe(true)
    expect(afterDeleteRight.rightBranches.map((b) => b.text)).toEqual(['L1'])
    expect(afterDeleteRight.leftBranches.map((b) => b.text)).toEqual(['L2'])

    // Clockwise reconstruct + redistribute is idempotent for a balanced split.
    const again = rebalanceMindMapBranchesIfLeftOnly(
      afterDeleteRight.leftBranches,
      afterDeleteRight.rightBranches
    )
    expect(again.redistributed).toBe(false)
  })

  it('leaves right-only maps alone (intentional structure mode)', () => {
    const result = rebalanceMindMapBranchesIfLeftOnly(
      [],
      [{ text: 'OnlyRight' }, { text: 'AlsoRight' }]
    )
    expect(result.redistributed).toBe(false)
    expect(result.rightBranches.map((b) => b.text)).toEqual(['OnlyRight', 'AlsoRight'])
    expect(result.leftBranches).toEqual([])
  })

  it('mindMapBranchesClockwiseOrder is the inverse of distributeBranchesClockwise', () => {
    const branches = [{ text: 'A' }, { text: 'B' }, { text: 'C' }, { text: 'D' }]
    const { rightBranches, leftBranches } = distributeBranchesClockwise(branches)
    expect(mindMapBranchesClockwiseOrder(rightBranches, leftBranches).map((b) => b.text)).toEqual([
      'A',
      'B',
      'C',
      'D',
    ])
  })
})
