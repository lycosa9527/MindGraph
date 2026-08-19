import { describe, expect, it } from 'vitest'

import { nodesAndConnectionsToMindMapSpec, findBranchByNodeId } from '@/stores/specLoader/mindMap'
import type { Connection, DiagramNode } from '@/types'
import {
  extractBranchesFromGeneratedSpec,
  mergeGeneratedBranchesIntoSpec,
  normalizeGeneratedBranch,
  toDirectChildrenOnly,
} from '@/utils/mindMapSubgraphMerge'

function node(id: string, text: string): DiagramNode {
  return { id, text, type: 'branch', position: { x: 0, y: 0 } }
}

function link(source: string, target: string): Connection {
  return { id: `${source}-${target}`, source, target }
}

describe('mergeGeneratedBranchesIntoSpec', () => {
  it('appends generated children under the selected branch', () => {
    const nodes: DiagramNode[] = [node('topic', 'Photosynthesis'), node('branch-r-1-0', 'Light')]
    const connections: Connection[] = [link('topic', 'branch-r-1-0')]
    const current = nodesAndConnectionsToMindMapSpec(nodes, connections)
    const merged = mergeGeneratedBranchesIntoSpec(current, 'branch-r-1-0', [
      { text: 'Photosystem II' },
      { text: 'Electron transport' },
    ], connections)
    expect(merged).not.toBeNull()
    if (!merged) return
    const branch = merged.rightBranches.find((b) => b.text === 'Light')
    expect(branch?.children?.map((c) => c.text)).toEqual(['Photosystem II', 'Electron transport'])
  })

  it('replaces placeholder children instead of appending beside them', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'History'),
      node('branch-r-1-0', 'Ancient'),
      node('branch-r-2-0', '输入文本'),
      node('branch-r-2-1', '输入文本'),
    ]
    const connections: Connection[] = [
      link('topic', 'branch-r-1-0'),
      link('branch-r-1-0', 'branch-r-2-0'),
      link('branch-r-1-0', 'branch-r-2-1'),
    ]
    const current = nodesAndConnectionsToMindMapSpec(nodes, connections)
    const merged = mergeGeneratedBranchesIntoSpec(current, 'branch-r-1-0', [
      { text: 'Dynasties' },
      { text: 'Culture' },
      { text: 'Economy' },
    ], connections)
    expect(merged).not.toBeNull()
    if (!merged) return
    const branch = merged.rightBranches.find((b) => b.text === 'Ancient')
    expect(branch?.children?.map((c) => c.text)).toEqual(['Dynasties', 'Culture', 'Economy'])
  })

  it('keeps real children and only replaces placeholder slots', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'History'),
      node('branch-r-1-0', 'Ancient'),
      node('branch-r-2-0', 'Dynasties'),
      node('branch-r-2-1', '输入文本'),
    ]
    const connections: Connection[] = [
      link('topic', 'branch-r-1-0'),
      link('branch-r-1-0', 'branch-r-2-0'),
      link('branch-r-1-0', 'branch-r-2-1'),
    ]
    const current = nodesAndConnectionsToMindMapSpec(nodes, connections)
    const merged = mergeGeneratedBranchesIntoSpec(current, 'branch-r-1-0', [{ text: 'Culture' }], connections)
    expect(merged).not.toBeNull()
    if (!merged) return
    const branch = merged.rightBranches.find((b) => b.text === 'Ancient')
    expect(branch?.children?.map((c) => c.text)).toEqual(['Dynasties', 'Culture'])
  })

  it('merges under a branch when node id indices have gaps', () => {
    const nodes: DiagramNode[] = [
      node('topic', '猫草'),
      node('branch-r-1-0', '历史'),
      node('branch-r-1-2', '喂养'),
    ]
    const connections: Connection[] = [
      link('topic', 'branch-r-1-0'),
      link('topic', 'branch-r-1-2'),
    ]
    const current = nodesAndConnectionsToMindMapSpec(nodes, connections)
    const merged = mergeGeneratedBranchesIntoSpec(
      current,
      'branch-r-1-2',
      [{ text: '干草' }, { text: '猫粮' }, { text: '清水' }],
      connections
    )
    expect(merged).not.toBeNull()
    if (!merged) return
    const branch = merged.rightBranches.find((b) => b.text === '喂养')
    expect(branch?.children?.map((c) => c.text)).toEqual(['干草', '猫粮', '清水'])
  })
})

describe('findBranchByNodeId', () => {
  it('resolves branches using actual diagram node ids (not regenerated counters)', () => {
    const nodes: DiagramNode[] = [
      node('topic', '猫草'),
      node('branch-r-1-0', '历史'),
      node('branch-r-1-2', '喂养'),
    ]
    const connections: Connection[] = [
      link('topic', 'branch-r-1-0'),
      link('topic', 'branch-r-1-2'),
    ]
    const spec = nodesAndConnectionsToMindMapSpec(nodes, connections)
    const found = findBranchByNodeId(
      spec.rightBranches,
      spec.leftBranches,
      'branch-r-1-2',
      connections
    )
    expect(found?.branch.text).toBe('喂养')
  })
})

describe('normalizeGeneratedBranch', () => {
  it('keeps bare string children as text objects', () => {
    const branch = normalizeGeneratedBranch({
      text: '光学原理',
      children: ['光场重建与相位编码', { text: '干涉记录' }],
    })
    expect(branch?.text).toBe('光学原理')
    expect(branch?.children?.map((child) => child.text)).toEqual([
      '光场重建与相位编码',
      '干涉记录',
    ])
    const fromSpec = extractBranchesFromGeneratedSpec({
      topic: '全息投影是什么',
      children: ['光场重建与相位编码'],
    })
    expect(fromSpec.map((item) => item.text)).toEqual(['光场重建与相位编码'])
  })
})

describe('toDirectChildrenOnly', () => {
  it('strips nested grandchildren from generated branches', () => {
    const flat = toDirectChildrenOnly([
      { text: 'Child A', children: [{ text: 'Grandchild' }] },
      { text: 'Child B' },
    ])
    expect(flat).toEqual([{ text: 'Child A' }, { text: 'Child B' }])
  })
})
