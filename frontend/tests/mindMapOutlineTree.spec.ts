import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { Connection, DiagramNode } from '@/types'
import {
  distributeBranchesClockwise,
  loadMindMapSpec,
  mindMapBranchesClockwiseOrder,
  nodesAndConnectionsToMindMapSpec,
} from '@/stores/specLoader/mindMap'
import { useUIStore } from '@/stores/ui'
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

/** Build a laid-out topic + L1 branches matching distributeBranchesClockwise stacks. */
function diagramFromClockwiseLabels(labels: string[]): {
  nodes: DiagramNode[]
  connections: Connection[]
  clockwise: string[]
} {
  const branches = labels.map((text) => ({ text }))
  const { rightBranches, leftBranches } = distributeBranchesClockwise(branches)
  const nodes: DiagramNode[] = [node('topic', '中心', 100, 'topic')]
  const connections: Connection[] = []
  let edge = 0
  // stackBranches walks each side top→bottom in array order.
  rightBranches.forEach((branch, i) => {
    const id = `branch-r-1-${i}`
    nodes.push(node(id, branch.text, 40 + i * 80))
    connections.push({ id: `e${edge++}`, source: 'topic', target: id })
  })
  leftBranches.forEach((branch, i) => {
    const id = `branch-l-1-${i}`
    nodes.push(node(id, branch.text, 40 + i * 80))
    connections.push({ id: `e${edge++}`, source: 'topic', target: id })
  })
  return {
    nodes,
    connections,
    clockwise: mindMapBranchesClockwiseOrder(rightBranches, leftBranches).map((b) => b.text),
  }
}

describe('buildMindMapOutlineTree', () => {
  it('orders topic children clockwise: right top→bottom, left bottom→top', () => {
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
    expect(flat.map((r) => r.text)).toEqual(['中心', '右上', '右下', '左下', '左上'])
  })

  it.each([1, 2, 3, 4, 5, 6, 7, 8])(
    'matches distributeBranchesClockwise reading order for %i L1 branches',
    (count) => {
      const labels = Array.from({ length: count }, (_, i) => String(i + 1))
      const { nodes, connections, clockwise } = diagramFromClockwiseLabels(labels)
      const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
      expect(flat.map((r) => r.text)).toEqual(['中心', ...clockwise])
      expect(clockwise).toEqual(labels)
    }
  )

  it('reverses left connection order when positions are missing (N=5)', () => {
    // Clockwise 1..5 → right [1,2,3], left stack top→bottom [5,4].
    const nodes: DiagramNode[] = [
      { id: 'topic', text: '中心', type: 'topic' },
      { id: 'branch-r-1-0', text: '1', type: 'branch' },
      { id: 'branch-r-1-1', text: '2', type: 'branch' },
      { id: 'branch-r-1-2', text: '3', type: 'branch' },
      { id: 'branch-l-1-0', text: '5', type: 'branch' },
      { id: 'branch-l-1-1', text: '4', type: 'branch' },
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'branch-r-1-0' },
      { id: 'e2', source: 'topic', target: 'branch-r-1-1' },
      { id: 'e3', source: 'topic', target: 'branch-r-1-2' },
      { id: 'e4', source: 'topic', target: 'branch-l-1-0' },
      { id: 'e5', source: 'topic', target: 'branch-l-1-1' },
    ]
    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual(['中心', '1', '2', '3', '4', '5'])
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

describe('buildMindMapOutlineTree vs loadMindMapSpec layouts', () => {
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
        dispatchEvent: vi.fn(() => false),
      }))
    )
    useUIStore().mindMapCanvasMode = 'v2'
  })

  it.each([1, 2, 3, 4, 5, 6, 7, 8])(
    'follows layout clockwise order after loadMindMapSpec with %i branches',
    (count) => {
      const children = Array.from({ length: count }, (_, i) => ({ text: String(i + 1) }))
      const { nodes, connections } = loadMindMapSpec({ topic: '中心', children })
      const extracted = nodesAndConnectionsToMindMapSpec(nodes, connections)
      const clockwise = mindMapBranchesClockwiseOrder(
        extracted.rightBranches,
        extracted.leftBranches
      ).map((b) => b.text)

      const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
      expect(flat.map((r) => r.text)).toEqual(['中心', ...clockwise])
      expect(clockwise).toEqual(children.map((c) => c.text))
    }
  )
})
