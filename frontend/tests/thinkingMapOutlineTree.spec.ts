import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode } from '@/types'
import { flattenMindMapOutline } from '@/utils/mindMapOutlineTree'
import { buildThinkingMapOutlineTree } from '@/utils/thinkingMapOutlineTree'

function node(
  id: string,
  text: string,
  type: DiagramNode['type'] = 'branch',
  data?: Record<string, unknown>
): DiagramNode {
  return { id, text, type, position: { x: 0, y: 0 }, data }
}

describe('buildThinkingMapOutlineTree', () => {
  it('lists circle contexts under the topic and skips the boundary', () => {
    const tree = buildThinkingMapOutlineTree(
      'circle_map',
      [
        node('outer-boundary', '', 'boundary'),
        node('topic', '水果', 'center'),
        node('c2', '香蕉', 'bubble', { groupIndex: 1 }),
        node('c1', '苹果', 'bubble', { groupIndex: 0 }),
      ],
      []
    )
    expect(flattenMindMapOutline(tree).map((row) => row.text)).toEqual(['水果', '苹果', '香蕉'])
  })

  it('lists bridge pairs under the relating factor, left then right', () => {
    const tree = buildThinkingMapOutlineTree(
      'bridge_map',
      [
        node('right-0', '热', 'branch', { pairIndex: 0, position: 'right' }),
        node('left-1', '作者', 'branch', { pairIndex: 1, position: 'left' }),
        node('left-0', '温度计', 'branch', { pairIndex: 0, position: 'left' }),
        node('dimension-label', '如同', 'label'),
        node('right-1', '书', 'branch', { pairIndex: 1, position: 'right' }),
      ],
      []
    )
    expect(flattenMindMapOutline(tree).map((row) => row.text)).toEqual([
      '如同',
      '温度计',
      '热',
      '作者',
      '书',
    ])
  })

  it('lists causes before effects even though causes point at the event', () => {
    const connections: Connection[] = [
      { id: 'c', source: 'cause-0', target: 'event' },
      { id: 'e', source: 'event', target: 'effect-0' },
    ]
    const tree = buildThinkingMapOutlineTree(
      'multi_flow_map',
      [
        node('event', '迟到', 'topic'),
        node('effect-0', '批评', 'flow', { multiFlowRole: 'effect', groupIndex: 0 }),
        node('cause-0', '堵车', 'flow', { multiFlowRole: 'cause', groupIndex: 0 }),
      ],
      connections
    )
    expect(flattenMindMapOutline(tree).map((row) => row.text)).toEqual(['迟到', '堵车', '批评'])
  })

  it('lists each double-bubble node once', () => {
    const tree = buildThinkingMapOutlineTree(
      'double_bubble_map',
      [
        node('left-topic', '猫', 'topic'),
        node('right-topic', '狗', 'topic'),
        node('sim', '宠物', 'bubble', { doubleBubbleRole: 'similarity', groupIndex: 0 }),
        node('ld', '爬树', 'bubble', { doubleBubbleRole: 'leftDiff', groupIndex: 0 }),
        node('rd', '汪汪', 'bubble', { doubleBubbleRole: 'rightDiff', groupIndex: 0 }),
      ],
      []
    )
    expect(flattenMindMapOutline(tree).map((row) => `${row.depth}:${row.text}`)).toEqual([
      '0:猫',
      '1:宠物',
      '1:爬树',
      '0:狗',
      '1:汪汪',
    ])
  })

  it('follows parent links on a bubble map', () => {
    const tree = buildThinkingMapOutlineTree(
      'bubble_map',
      [node('topic', '夏天', 'topic'), node('hot', '热', 'bubble'), node('label', '维度', 'label')],
      [{ id: 'e', source: 'topic', target: 'hot' }]
    )
    expect(flattenMindMapOutline(tree).map((row) => row.text)).toEqual(['夏天', '热'])
  })
})
