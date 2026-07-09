import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode } from '@/types'
import {
  collectMindMapSubgraphContext,
  formatMindMapSubgraphPrompt,
  isMindMapSubgraphExpandable,
} from '@/utils/mindMapSubgraphContext'

function node(id: string, text: string): DiagramNode {
  return { id, text, type: 'branch', position: { x: 0, y: 0 } }
}

function link(source: string, target: string): Connection {
  return { id: `${source}-${target}`, source, target }
}

describe('collectMindMapSubgraphContext', () => {
  it('returns null for the central topic node', () => {
    const nodes: DiagramNode[] = [node('topic', 'Photosynthesis')]
    const connections: Connection[] = []
    expect(collectMindMapSubgraphContext(nodes, connections, 'topic')).toBeNull()
  })

  it('marks top-level branches as main-branch anchors', () => {
    const nodes: DiagramNode[] = [node('topic', 'History'), node('branch-r-1-0', 'Ancient')]
    const connections: Connection[] = [link('topic', 'branch-r-1-0')]
    const ctx = collectMindMapSubgraphContext(nodes, connections, 'branch-r-1-0')
    expect(ctx?.isMainBranch).toBe(true)
    expect(ctx?.parentBranch).toBeUndefined()
  })

  it('marks nested nodes as child anchors with parent branch', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'History'),
      node('branch-r-1-0', 'Ancient'),
      node('branch-r-2-0', 'Dynasties'),
    ]
    const connections: Connection[] = [
      link('topic', 'branch-r-1-0'),
      link('branch-r-1-0', 'branch-r-2-0'),
    ]
    const ctx = collectMindMapSubgraphContext(nodes, connections, 'branch-r-2-0')
    expect(ctx?.isMainBranch).toBe(false)
    expect(ctx?.parentBranch).toBe('Ancient')
  })

  it('collects topic, sibling top-level branches, and existing children', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'Photosynthesis'),
      node('branch-r-1-0', 'Light'),
      node('branch-r-1-1', 'Calvin cycle'),
      node('branch-r-2-0', 'Chlorophyll'),
    ]
    const connections: Connection[] = [
      link('topic', 'branch-r-1-0'),
      link('topic', 'branch-r-1-1'),
      link('branch-r-1-0', 'branch-r-2-0'),
    ]

    const ctx = collectMindMapSubgraphContext(nodes, connections, 'branch-r-1-0')
    expect(ctx).toEqual({
      topic: 'Photosynthesis',
      expandBranch: 'Light',
      referenceBranches: ['Calvin cycle'],
      existingChildren: ['Chlorophyll'],
      parentBranch: undefined,
      isMainBranch: true,
    })
  })

  it('includes parent branch and siblings for nested anchors', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'Animals'),
      node('branch-r-1-0', 'Mammals'),
      node('branch-r-1-1', 'Birds'),
      node('branch-r-2-0', 'Primates'),
      node('branch-r-3-0', 'Rodents'),
    ]
    const connections: Connection[] = [
      link('topic', 'branch-r-1-0'),
      link('topic', 'branch-r-1-1'),
      link('branch-r-1-0', 'branch-r-2-0'),
      link('branch-r-1-0', 'branch-r-3-0'),
    ]

    const ctx = collectMindMapSubgraphContext(nodes, connections, 'branch-r-2-0')
    expect(ctx?.topic).toBe('Animals')
    expect(ctx?.expandBranch).toBe('Primates')
    expect(ctx?.parentBranch).toBe('Mammals')
    expect(ctx?.referenceBranches).toEqual(expect.arrayContaining(['Rodents', 'Birds']))
    expect(ctx?.existingChildren).toEqual([])
  })

  it('formats a rich branch-expand prompt with topic and sibling branches', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'Photosynthesis'),
      node('branch-r-1-0', 'Light'),
      node('branch-r-1-1', 'Calvin cycle'),
      node('branch-r-2-0', 'Chlorophyll'),
    ]
    const connections: Connection[] = [
      link('topic', 'branch-r-1-0'),
      link('topic', 'branch-r-1-1'),
      link('branch-r-1-0', 'branch-r-2-0'),
    ]

    const ctx = collectMindMapSubgraphContext(nodes, connections, 'branch-r-1-0')
    expect(ctx).not.toBeNull()
    const prompt = formatMindMapSubgraphPrompt(ctx!, 'zh')
    expect(prompt).toContain('中心主题：Photosynthesis')
    expect(prompt).toContain('要扩展的分支：Light')
    expect(prompt).toContain('图中其他分支（参考）：Calvin cycle')
    expect(prompt).toContain('该分支已有子节点（勿重复）：Chlorophyll')
    expect(prompt).toContain('直接子节点')
  })

  it('uses nested-child wording for deeper anchors', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'History'),
      node('branch-r-1-0', 'Ancient'),
      node('branch-r-2-0', 'Dynasties'),
    ]
    const connections: Connection[] = [
      link('topic', 'branch-r-1-0'),
      link('branch-r-1-0', 'branch-r-2-0'),
    ]
    const ctx = collectMindMapSubgraphContext(nodes, connections, 'branch-r-2-0')
    const prompt = formatMindMapSubgraphPrompt(ctx!, 'zh')
    expect(prompt).toContain('上级分支：Ancient')
    expect(prompt).toContain('直接下级节点')
  })
})

describe('isMindMapSubgraphExpandable', () => {
  it('returns false for topic and empty selection', () => {
    expect(isMindMapSubgraphExpandable(null)).toBe(false)
    expect(isMindMapSubgraphExpandable('topic')).toBe(false)
  })

  it('returns true for branch nodes', () => {
    expect(isMindMapSubgraphExpandable('branch-r-1-0')).toBe(true)
  })
})
