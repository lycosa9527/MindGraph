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
    { id: 'branch-r-1-0', text: '分支A', type: 'branch', position: { x: 200, y: 0 } },
    { id: 'branch-r-2-0', text: '子A1', type: 'branch', position: { x: 360, y: -20 } },
    { id: 'branch-r-2-1', text: '子A2', type: 'branch', position: { x: 360, y: 20 } },
    { id: 'branch-l-1-0', text: '分支B', type: 'branch', position: { x: -200, y: 0 } },
  ]
  const connections: Connection[] = [
    { id: 'e1', source: 'topic', target: 'branch-r-1-0' },
    { id: 'e2', source: 'branch-r-1-0', target: 'branch-r-2-0' },
    { id: 'e3', source: 'branch-r-1-0', target: 'branch-r-2-1' },
    { id: 'e4', source: 'topic', target: 'branch-l-1-0' },
  ]
  const descendants = (id: string) => getDescendantIds(id, connections)

  it('builds overview plus first-level branches by default', () => {
    const slides = buildMindMapSlides(nodes, connections, descendants)
    expect(slides.map((slide) => slide.id)).toEqual([
      'overview',
      'branch-r-1-0',
      'branch-l-1-0',
    ])
    expect(slides[0]?.branchNodeId).toBe('topic')
    expect(slides[0]?.breadcrumb).toEqual(['中心'])
  })

  it('includes breadcrumb path for branch slides', () => {
    const slides = buildMindMapSlides(nodes, connections, descendants, 'deep')
    const childSlide = slides.find((slide) => slide.id === 'branch-r-2-0')
    expect(childSlide?.breadcrumb).toEqual(['中心', '分支A', '子A1'])
  })

  it('depth traversal includes every branch node after overview', () => {
    const slides = buildMindMapSlides(nodes, connections, descendants, 'deep')
    expect(slides.map((slide) => slide.id)).toEqual([
      'overview',
      'branch-r-1-0',
      'branch-r-2-0',
      'branch-r-2-1',
      'branch-l-1-0',
    ])
  })

  it('focuses each deep slide on the node and its descendants', () => {
    const slides = buildMindMapSlides(nodes, connections, descendants, 'deep')
    const childSlide = slides.find((slide) => slide.id === 'branch-r-2-0')
    expect(childSlide?.focusNodeIds).toEqual(['branch-r-2-0'])
  })
})
