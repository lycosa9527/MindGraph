import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode } from '@/types'
import { BRACE_DIMENSION_LABEL_ID, BRACE_WHOLE_NODE_ID } from '@/utils/braceMapIdentity'
import { buildBraceMapSlides } from '@/utils/braceMapSlides'

function node(id: string, text: string, type: DiagramNode['type'] = 'brace'): DiagramNode {
  return { id, text, type, position: { x: 0, y: 0 } }
}

function edge(source: string, target: string): Connection {
  return { id: `${source}-${target}`, source, target }
}

const nodes: DiagramNode[] = [
  node(BRACE_WHOLE_NODE_ID, '整体', 'topic'),
  node(BRACE_DIMENSION_LABEL_ID, '维度', 'label'),
  node('a', '部分A'),
  node('a1', '子A1'),
  node('a1a', '孙A1a'),
  node('b', '部分B'),
]

const connections: Connection[] = [
  edge(BRACE_WHOLE_NODE_ID, 'a'),
  edge('a', 'a1'),
  edge('a1', 'a1a'),
  edge(BRACE_WHOLE_NODE_ID, 'b'),
]

describe('buildBraceMapSlides', () => {
  it('walks each part and keeps descendants in the part frame', () => {
    const slides = buildBraceMapSlides(nodes, connections, 'firstLevel')
    expect(slides.map((slide) => slide.id)).toEqual(['overview', 'a', 'b'])
    expect(slides[0]?.focusNodeIds).not.toContain(BRACE_DIMENSION_LABEL_ID)
    expect(slides[1]?.focusNodeIds).toEqual(['a', 'a1', 'a1a'])
    expect(slides[1]?.breadcrumb).toEqual(['整体', '部分A'])
    expect(slides[2]?.focusNodeIds).toEqual(['b'])
  })

  it('visits every descendant in deep mode, framed from its part', () => {
    const slides = buildBraceMapSlides(nodes, connections, 'deep')
    expect(slides.map((slide) => slide.id)).toEqual(['overview', 'a', 'a1', 'a1a', 'b'])
    expect(slides[2]?.focusNodeIds).toEqual(['a', 'a1', 'a1a'])
    expect(slides[3]?.breadcrumb).toEqual(['整体', '部分A', '子A1', '孙A1a'])
    expect(slides[3]?.focusNodeIds).toEqual(['a', 'a1', 'a1a'])
  })
})
