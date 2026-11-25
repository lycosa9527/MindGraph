import { describe, expect, it } from 'vitest'

import {
  type DragPracticeNode,
  dragPracticeResolveDrop,
  dragPracticeSlotGroup,
} from '@/composables/mindMap/dragPracticeMatch'

describe('dragPracticeSlotGroup', () => {
  it('groups double-bubble differences by column, not by index', () => {
    const nodes = [
      { id: 'l1', data: { doubleBubbleRole: 'leftDiff' } },
      { id: 'l2', data: { doubleBubbleRole: 'leftDiff' } },
      { id: 'r1', data: { doubleBubbleRole: 'rightDiff' } },
      { id: 's1', data: { doubleBubbleRole: 'similarity' } },
    ]
    expect(dragPracticeSlotGroup('double_bubble_map', 'l1', nodes, [])).toBe(
      dragPracticeSlotGroup('double_bubble_map', 'l2', nodes, [])
    )
    expect(dragPracticeSlotGroup('double_bubble_map', 'l1', nodes, [])).not.toBe(
      dragPracticeSlotGroup('double_bubble_map', 'r1', nodes, [])
    )
    expect(dragPracticeSlotGroup('double_bubble_map', 's1', nodes, [])).toBe('role:similarity')
  })

  it('keeps flow steps on their own slot', () => {
    const nodes = [
      { id: 's1', parentId: 'flow-topic' },
      { id: 's2', parentId: 'flow-topic' },
    ]
    expect(dragPracticeSlotGroup('flow_map', 's1', nodes, [])).toBe('node:s1')
    expect(dragPracticeSlotGroup('flow_map', 's2', nodes, [])).toBe('node:s2')
  })

  it('groups mind-map siblings that share a parent', () => {
    const nodes = [
      { id: 'a', parentId: 'topic' },
      { id: 'b', parentId: 'topic' },
      { id: 'c', parentId: 'a' },
    ]
    expect(dragPracticeSlotGroup('mind_map', 'a', nodes, [])).toBe('parent:topic')
    expect(dragPracticeSlotGroup('mind_map', 'b', nodes, [])).toBe('parent:topic')
    expect(dragPracticeSlotGroup('mind_map', 'c', nodes, [])).toBe('parent:a')
  })
})

function diffNode(
  id: string,
  role: 'similarity' | 'leftDiff' | 'rightDiff',
  index: number
): DragPracticeNode {
  return { id, data: { doubleBubbleRole: role, groupIndex: index } }
}

const doubleBubbleNodes: DragPracticeNode[] = [
  diffNode('s0', 'similarity', 0),
  diffNode('s1', 'similarity', 1),
  diffNode('l0', 'leftDiff', 0),
  diffNode('r0', 'rightDiff', 0),
  diffNode('l1', 'leftDiff', 1),
  diffNode('r1', 'rightDiff', 1),
]

const doubleBubbleAnswers: Record<string, string> = {
  s0: '都会飞',
  s1: '有翅膀',
  l0: '便宜',
  r0: '贵',
  l1: '小',
  r1: '大',
}

describe('dragPracticeResolveDrop double bubble', () => {
  it('lets similarities trade places in every blank mode', () => {
    const resolved = dragPracticeResolveDrop(
      'double_bubble_map',
      's0',
      '有翅膀',
      doubleBubbleNodes,
      [],
      ['s0', 's1'],
      [],
      doubleBubbleAnswers
    )
    expect(resolved?.sourceId).toBe('s1')
    expect(resolved?.answers.s0).toBe('有翅膀')
    expect(resolved?.answers.s1).toBe('都会飞')
    expect(resolved?.answers.l0).toBe('便宜')
  })

  it('moves a fully blank difference pair onto another open row', () => {
    const blanks = ['l0', 'r0', 'l1', 'r1']
    const moved = dragPracticeResolveDrop(
      'double_bubble_map',
      'l0',
      '小',
      doubleBubbleNodes,
      [],
      blanks,
      [],
      doubleBubbleAnswers
    )
    expect(moved?.answers.l0).toBe('小')
    expect(moved?.answers.r0).toBe('大')
    expect(moved?.answers.l1).toBe('便宜')
    expect(moved?.answers.r1).toBe('贵')

    const broken = dragPracticeResolveDrop(
      'double_bubble_map',
      'r0',
      '贵',
      doubleBubbleNodes,
      [],
      blanks,
      ['l0'],
      moved?.answers ?? doubleBubbleAnswers
    )
    expect(broken).toBeNull()

    const partner = dragPracticeResolveDrop(
      'double_bubble_map',
      'r0',
      '大',
      doubleBubbleNodes,
      [],
      blanks,
      ['l0'],
      moved?.answers ?? doubleBubbleAnswers
    )
    expect(partner?.sourceId).toBe('r0')
  })

  it('anchors a pair when the other side is still visible', () => {
    const blanks = ['l0', 'l1']
    expect(
      dragPracticeResolveDrop(
        'double_bubble_map',
        'l0',
        '小',
        doubleBubbleNodes,
        [],
        blanks,
        [],
        doubleBubbleAnswers
      )
    ).toBeNull()
    expect(
      dragPracticeResolveDrop(
        'double_bubble_map',
        'l0',
        '便宜',
        doubleBubbleNodes,
        [],
        blanks,
        [],
        doubleBubbleAnswers
      )?.sourceId
    ).toBe('l0')
  })

  it('rejects a left difference dropped on the right side', () => {
    expect(
      dragPracticeResolveDrop(
        'double_bubble_map',
        'r0',
        '便宜',
        doubleBubbleNodes,
        [],
        ['l0', 'r0', 'l1', 'r1'],
        [],
        doubleBubbleAnswers
      )
    ).toBeNull()
  })
})

function edge(source: string, target: string): { source: string; target: string } {
  return { source, target }
}

describe('dragPracticeResolveDrop other diagrams', () => {
  it('lets circle contexts trade and keeps the topic fixed', () => {
    const nodes: DragPracticeNode[] = [
      { id: 'topic', type: 'center' },
      { id: 'c0', type: 'bubble' },
      { id: 'c1', type: 'bubble' },
    ]
    const answers = { c0: '学校', c1: '家庭' }
    const moved = dragPracticeResolveDrop(
      'circle_map',
      'c0',
      '家庭',
      nodes,
      [],
      ['c0', 'c1'],
      [],
      answers
    )
    expect(moved?.answers.c0).toBe('家庭')
    expect(moved?.answers.c1).toBe('学校')
    expect(
      dragPracticeResolveDrop('circle_map', 'topic', '家庭', nodes, [], ['topic', 'c0'], [], {
        topic: '我',
        ...answers,
      })
    ).toBeNull()
  })

  it('keeps bubble attributes in one set', () => {
    const nodes: DragPracticeNode[] = [
      { id: 'topic', type: 'topic' },
      { id: 'a0', type: 'bubble' },
      { id: 'a1', type: 'bubble' },
    ]
    const moved = dragPracticeResolveDrop('bubble_map', 'a0', '温暖', nodes, [], ['a0', 'a1'], [], {
      a0: '明亮',
      a1: '温暖',
    })
    expect(moved?.sourceId).toBe('a1')
  })

  it('separates multi-flow causes from effects', () => {
    const nodes: DragPracticeNode[] = [
      { id: 'c0', data: { multiFlowRole: 'cause', groupIndex: 0 } },
      { id: 'c1', data: { multiFlowRole: 'cause', groupIndex: 1 } },
      { id: 'e0', data: { multiFlowRole: 'effect', groupIndex: 0 } },
    ]
    const answers = { c0: '下雨', c1: '降温', e0: '地滑' }
    const blanks = ['c0', 'c1', 'e0']
    expect(
      dragPracticeResolveDrop('multi_flow_map', 'c0', '降温', nodes, [], blanks, [], answers)
        ?.answers.c0
    ).toBe('降温')
    expect(
      dragPracticeResolveDrop('multi_flow_map', 'e0', '下雨', nodes, [], blanks, [], answers)
    ).toBeNull()
  })

  it('moves a bridge analogy only as a pair', () => {
    const nodes: DragPracticeNode[] = [
      { id: 'l0', data: { pairIndex: 0, position: 'left' } },
      { id: 'r0', data: { pairIndex: 0, position: 'right' } },
      { id: 'l1', data: { pairIndex: 1, position: 'left' } },
      { id: 'r1', data: { pairIndex: 1, position: 'right' } },
    ]
    const answers = { l0: '画家', r0: '画笔', l1: '作家', r1: '钢笔' }
    const blanks = ['l0', 'r0', 'l1', 'r1']
    const moved = dragPracticeResolveDrop(
      'bridge_map',
      'l0',
      '作家',
      nodes,
      [],
      blanks,
      [],
      answers
    )
    expect(moved?.answers).toMatchObject({ l0: '作家', r0: '钢笔', l1: '画家', r1: '画笔' })
    expect(
      dragPracticeResolveDrop(
        'bridge_map',
        'r0',
        '画笔',
        nodes,
        [],
        blanks,
        ['l0'],
        moved?.answers ?? answers
      )
    ).toBeNull()
    expect(
      dragPracticeResolveDrop('bridge_map', 'l0', '作家', nodes, [], ['l0', 'l1'], [], answers)
    ).toBeNull()
  })

  it('keeps tree items inside their category and moves a category with its items', () => {
    const nodes: DragPracticeNode[] = [
      { id: 'root' },
      { id: 'cat0' },
      { id: 'cat1' },
      { id: 'a0' },
      { id: 'a1' },
      { id: 'b0' },
      { id: 'b1' },
    ]
    const connections = [
      edge('root', 'cat0'),
      edge('root', 'cat1'),
      edge('cat0', 'a0'),
      edge('cat0', 'a1'),
      edge('cat1', 'b0'),
      edge('cat1', 'b1'),
    ]
    const answers = {
      cat0: '水果',
      cat1: '蔬菜',
      a0: '苹果',
      a1: '香蕉',
      b0: '白菜',
      b1: '萝卜',
    }
    const itemSwap = dragPracticeResolveDrop(
      'tree_map',
      'a0',
      '香蕉',
      nodes,
      connections,
      ['a0', 'a1'],
      [],
      answers
    )
    expect(itemSwap?.answers.a0).toBe('香蕉')
    expect(
      dragPracticeResolveDrop(
        'tree_map',
        'a0',
        '白菜',
        nodes,
        connections,
        ['a0', 'b0'],
        [],
        answers
      )
    ).toBeNull()
    expect(
      dragPracticeResolveDrop(
        'tree_map',
        'cat0',
        '蔬菜',
        nodes,
        connections,
        ['cat0', 'cat1'],
        [],
        answers
      )
    ).toBeNull()
    const moved = dragPracticeResolveDrop(
      'tree_map',
      'cat0',
      '蔬菜',
      nodes,
      connections,
      ['cat0', 'cat1', 'a0', 'a1', 'b0', 'b1'],
      [],
      answers
    )
    expect(moved?.answers).toMatchObject({
      cat0: '蔬菜',
      a0: '白菜',
      a1: '萝卜',
      cat1: '水果',
      b0: '苹果',
      b1: '香蕉',
    })
  })

  it('anchors a mind-map branch while a child is still visible', () => {
    const nodes: DragPracticeNode[] = [
      { id: 'branch0', parentId: 'topic' },
      { id: 'branch1', parentId: 'topic' },
      { id: 'child0', parentId: 'branch0' },
      { id: 'child1', parentId: 'branch1' },
    ]
    const answers = { branch0: '学习', branch1: '运动', child0: '阅读', child1: '跑步' }
    expect(
      dragPracticeResolveDrop(
        'mind_map',
        'branch0',
        '运动',
        nodes,
        [],
        ['branch0', 'branch1'],
        [],
        answers
      )
    ).toBeNull()
    const moved = dragPracticeResolveDrop(
      'mind_map',
      'branch0',
      '运动',
      nodes,
      [],
      ['branch0', 'branch1', 'child0', 'child1'],
      [],
      answers
    )
    expect(moved?.answers).toMatchObject({
      branch0: '运动',
      child0: '跑步',
      branch1: '学习',
      child1: '阅读',
    })
  })

  it('keeps flow steps and concept nodes on their own slots', () => {
    const flow = dragPracticeResolveDrop(
      'flow_map',
      's0',
      '第二步',
      [
        { id: 's0', parentId: 'flow-topic' },
        { id: 's1', parentId: 'flow-topic' },
      ],
      [],
      ['s0', 's1'],
      [],
      { s0: '第一步', s1: '第二步' }
    )
    expect(flow).toBeNull()
    const concept = dragPracticeResolveDrop(
      'concept_map',
      'n0',
      '概念B',
      [{ id: 'n0' }, { id: 'n1' }],
      [],
      ['n0', 'n1'],
      [],
      { n0: '概念A', n1: '概念B' }
    )
    expect(concept).toBeNull()
  })
})
