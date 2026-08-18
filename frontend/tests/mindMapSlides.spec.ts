import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode } from '@/types'
import { buildMindMapSlides } from '@/utils/mindMapSlides'

function getDescendantIds(rootId: string, connections: Connection[]): Set<string> {
  const result = new Set<string>([rootId])
  const queue = [rootId]
  while (queue.length > 0) {
    const current = queue.shift()!
    for (const conn of connections) {
      if (conn.source === current && !result.has(conn.target)) {
        result.add(conn.target)
        queue.push(conn.target)
      }
    }
  }
  return result
}

describe('buildMindMapSlides', () => {
  const nodes: DiagramNode[] = [
    { id: 'topic', text: '中心', type: 'topic', position: { x: 0, y: 0 } },
    { id: 'uid-a', text: '分支A', type: 'branch', position: { x: 200, y: 0 } },
    { id: 'uid-a1', text: '子A1', type: 'branch', position: { x: 360, y: -20 } },
    { id: 'uid-a2', text: '子A2', type: 'branch', position: { x: 360, y: 20 } },
    { id: 'uid-b', text: '分支B', type: 'branch', position: { x: -200, y: 0 } },
  ]
  const connections: Connection[] = [
    { id: 'e1', source: 'topic', target: 'uid-a' },
    { id: 'e2', source: 'uid-a', target: 'uid-a1' },
    { id: 'e3', source: 'uid-a', target: 'uid-a2' },
    { id: 'e4', source: 'topic', target: 'uid-b' },
  ]
  const descendants = (id: string) => getDescendantIds(id, connections)

  it('builds overview plus first-level branches by default', () => {
    const slides = buildMindMapSlides(nodes, connections, descendants)
    expect(slides.map((slide) => slide.id)).toEqual(['overview', 'uid-a', 'uid-b'])
    expect(slides[0]?.branchNodeId).toBe('topic')
    expect(slides[0]?.breadcrumb).toEqual(['中心'])
  })

  it('includes breadcrumb path for branch slides', () => {
    const slides = buildMindMapSlides(nodes, connections, descendants, 'deep')
    const childSlide = slides.find((slide) => slide.id === 'uid-a1')
    expect(childSlide?.breadcrumb).toEqual(['中心', '分支A', '子A1'])
  })

  it('depth traversal includes every branch node after overview', () => {
    const slides = buildMindMapSlides(nodes, connections, descendants, 'deep')
    expect(slides.map((slide) => slide.id)).toEqual([
      'overview',
      'uid-a',
      'uid-a1',
      'uid-a2',
      'uid-b',
    ])
  })

  it('depth traversal walks left branches bottom→top (clockwise)', () => {
    const clockwiseNodes: DiagramNode[] = [
      { id: 'topic', text: '中心', type: 'topic', position: { x: 0, y: 100 } },
      { id: 'uid-1', text: '1', type: 'branch', position: { x: 200, y: 40 } },
      { id: 'uid-2', text: '2', type: 'branch', position: { x: 200, y: 200 } },
      { id: 'uid-4', text: '4', type: 'branch', position: { x: -200, y: 40 } },
      { id: 'uid-3', text: '3', type: 'branch', position: { x: -200, y: 200 } },
    ]
    const clockwiseConnections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'uid-1' },
      { id: 'e2', source: 'topic', target: 'uid-2' },
      { id: 'e3', source: 'topic', target: 'uid-4' },
      { id: 'e4', source: 'topic', target: 'uid-3' },
    ]
    const slides = buildMindMapSlides(
      clockwiseNodes,
      clockwiseConnections,
      (id) => getDescendantIds(id, clockwiseConnections),
      'deep'
    )
    expect(slides.map((slide) => slide.id)).toEqual([
      'overview',
      'uid-1',
      'uid-2',
      'uid-3',
      'uid-4',
    ])
  })

  it('focuses each deep slide on the node and its descendants', () => {
    const slides = buildMindMapSlides(nodes, connections, descendants, 'deep')
    const childSlide = slides.find((slide) => slide.id === 'uid-a1')
    expect(childSlide?.focusNodeIds).toEqual(['uid-a1'])
  })
})
