import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode } from '@/types'
import {
  buildMindMapOutlineTree,
  flattenMindMapOutline,
} from '@/utils/mindMapOutlineTree'

function node(
  id: string,
  text: string,
  y: number,
  type: DiagramNode['type'] = 'branch'
): DiagramNode {
  return {
    id,
    text,
    type,
    position: { x: 0, y },
  }
}

describe('buildMindMapOutlineTree', () => {
  it('orders siblings by canvas Y even when connection order disagrees', () => {
    const nodes: DiagramNode[] = [
      node('topic', '中心', 100, 'topic'),
      node('branch-r-1-0', '右下', 200),
      node('branch-r-1-1', '右上', 40),
      node('branch-l-1-0', '左下', 220),
      node('branch-l-1-1', '左上', 50),
    ]
    // Connection order intentionally inverted vs visual top→bottom.
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'branch-r-1-0' },
      { id: 'e2', source: 'topic', target: 'branch-r-1-1' },
      { id: 'e3', source: 'topic', target: 'branch-l-1-0' },
      { id: 'e4', source: 'topic', target: 'branch-l-1-1' },
    ]

    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual(['中心', '右上', '右下', '左上', '左下'])
  })

  it('orders nested children top→bottom by Y', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'T', 100, 'topic'),
      node('branch-r-1-0', 'Parent', 80),
      node('branch-r-2-0', 'ChildB', 160),
      node('branch-r-2-1', 'ChildA', 90),
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'branch-r-1-0' },
      { id: 'e2', source: 'branch-r-1-0', target: 'branch-r-2-0' },
      { id: 'e3', source: 'branch-r-1-0', target: 'branch-r-2-1' },
    ]

    const parent = buildMindMapOutlineTree(nodes, connections)[0]?.children[0]
    expect(parent?.children.map((c) => c.text)).toEqual(['ChildA', 'ChildB'])
  })

  it('falls back to connection order when positions are missing', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic' },
      { id: 'branch-r-1-0', text: 'First', type: 'branch' },
      { id: 'branch-r-1-1', text: 'Second', type: 'branch' },
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'branch-r-1-0' },
      { id: 'e2', source: 'topic', target: 'branch-r-1-1' },
    ]

    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual(['T', 'First', 'Second'])
  })

  it('reflects live text labels from the diagram nodes', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'Old topic', 0, 'topic'),
      node('branch-r-1-0', 'Old branch', 40),
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'branch-r-1-0' },
    ]

    nodes[0] = { ...nodes[0], text: 'New topic' }
    nodes[1] = { ...nodes[1], text: 'New branch' }

    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual(['New topic', 'New branch'])
  })
})
