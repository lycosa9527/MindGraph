import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode } from '@/types'
import { nodesInLearningSheetReadingOrder } from '@/utils/learningSheetAnswerOrder'

function node(
  id: string,
  text: string,
  type: DiagramNode['type'],
  x: number,
  y: number
): DiagramNode {
  return { id, text, type, position: { x, y } }
}

function edge(id: string, source: string, target: string): Connection {
  return { id, source, target }
}

describe('nodesInLearningSheetReadingOrder', () => {
  it('lists mind-map branches by column, not nodes-array order', () => {
    const nodes = [
      node('topic', '主题', 'topic', 200, 100),
      node('left-top', '左上', 'branch', 0, 20),
      node('right-bottom', '右下', 'branch', 400, 180),
      node('left-bottom', '左下', 'branch', 0, 180),
      node('right-top', '右上', 'branch', 400, 20),
    ]
    const connections = [
      edge('e1', 'topic', 'left-top'),
      edge('e2', 'topic', 'left-bottom'),
      edge('e3', 'topic', 'right-bottom'),
      edge('e4', 'topic', 'right-top'),
    ]
    const ordered = nodesInLearningSheetReadingOrder(nodes, connections, 'mindmap')
    expect(ordered.map((item) => item.id)).toEqual([
      'topic',
      'right-top',
      'right-bottom',
      'left-top',
      'left-bottom',
    ])
  })

  it('continues the left column clockwise when branch numbering is on', () => {
    const nodes = [
      node('topic', '主题', 'topic', 200, 100),
      node('left-top', '左上', 'branch', 0, 20),
      node('right-bottom', '右下', 'branch', 400, 180),
      node('left-bottom', '左下', 'branch', 0, 180),
      node('right-top', '右上', 'branch', 400, 20),
    ]
    const connections = [
      edge('e1', 'topic', 'left-top'),
      edge('e2', 'topic', 'left-bottom'),
      edge('e3', 'topic', 'right-bottom'),
      edge('e4', 'topic', 'right-top'),
    ]
    const ordered = nodesInLearningSheetReadingOrder(nodes, connections, 'mind_map', true)
    expect(ordered.map((item) => item.id)).toEqual([
      'topic',
      'right-top',
      'right-bottom',
      'left-bottom',
      'left-top',
    ])
  })

  it('finishes a branch before the next sibling', () => {
    const nodes = [
      node('topic', '主题', 'topic', 200, 100),
      node('right-low', '右下', 'branch', 400, 200),
      node('child-low', '子下', 'branch', 520, 80),
      node('right-high', '右上', 'branch', 400, 20),
      node('child-high', '子上', 'branch', 520, 0),
    ]
    const connections = [
      edge('e1', 'topic', 'right-low'),
      edge('e2', 'topic', 'right-high'),
      edge('e3', 'right-high', 'child-low'),
      edge('e4', 'right-high', 'child-high'),
    ]
    const ordered = nodesInLearningSheetReadingOrder(nodes, connections, 'mindmap')
    expect(ordered.map((item) => item.id)).toEqual([
      'topic',
      'right-high',
      'child-high',
      'child-low',
      'right-low',
    ])
  })

  it('matches numbered branch order before positions exist', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: '中心', type: 'topic' },
      { id: 'branch-r-1-0', text: '1', type: 'branch' },
      { id: 'branch-r-1-1', text: '2', type: 'branch' },
      { id: 'branch-r-1-2', text: '3', type: 'branch' },
      { id: 'branch-l-1-0', text: '5', type: 'branch' },
      { id: 'branch-l-1-1', text: '4', type: 'branch' },
    ]
    const connections = [
      edge('e1', 'topic', 'branch-r-1-0'),
      edge('e2', 'topic', 'branch-r-1-1'),
      edge('e3', 'topic', 'branch-r-1-2'),
      edge('e4', 'topic', 'branch-l-1-0'),
      edge('e5', 'topic', 'branch-l-1-1'),
    ]
    const numbered = nodesInLearningSheetReadingOrder(nodes, connections, 'mindmap', true)
    expect(numbered.map((item) => item.text)).toEqual(['中心', '1', '2', '3', '4', '5'])
    const reading = nodesInLearningSheetReadingOrder(nodes, connections, 'mindmap')
    expect(reading.map((item) => item.text)).toEqual(['中心', '1', '2', '3', '5', '4'])
  })

  it('lists non-mind-map nodes top to bottom, then left to right', () => {
    const nodes = [
      node('c', '下', 'flow', 40, 200),
      node('a', '上右', 'flow', 80, 10),
      node('b', '上左', 'flow', 10, 10),
    ]
    const ordered = nodesInLearningSheetReadingOrder(nodes, [], 'flow')
    expect(ordered.map((item) => item.id)).toEqual(['b', 'a', 'c'])
  })
})
