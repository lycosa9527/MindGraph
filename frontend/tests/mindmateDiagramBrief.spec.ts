import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode, NodeType } from '@/types'
import { buildMindmateDiagramBrief, withMindmateDiagramBrief } from '@/utils/mindmateDiagramBrief'
import { displayMindmateUserQueryForUi } from '@/utils/mindmateExtensionPageContext'

const zh: Record<string, string> = {
  'mindmate.diagramContext.childJoiner': '、',
  'mindmate.diagramContext.childWrap': '{text}（{children}）',
  'mindmate.diagramContext.purpose.circle_map': '圆圈图用来围绕一个中心词展开联想。',
  'mindmate.diagramContext.purpose.bubble_map': '气泡图用来描述一个事物的特征。',
  'mindmate.diagramContext.purpose.double_bubble_map': '双气泡图用来比较两个事物的相同点与不同点。',
  'mindmate.diagramContext.purpose.tree_map': '树形图用来按一个标准给事物分类。',
  'mindmate.diagramContext.purpose.brace_map': '括号图用来把一个整体拆成它的组成部分。',
  'mindmate.diagramContext.purpose.flow_map': '流程图用来按顺序列出一个过程的步骤。',
  'mindmate.diagramContext.purpose.multi_flow_map': '复流程图用来分析一个事件的原因和结果。',
  'mindmate.diagramContext.purpose.bridge_map': '桥形图用来用一组类比说明同一种关系。',
  'mindmate.diagramContext.purpose.concept_map':
    '概念图用来把概念以及概念之间的关系组织成知识结构。',
  'mindmate.diagramContext.purpose.mindmap': '思维导图用来从一个中心主题向外分层展开。',
  'mindmate.diagramContext.field.center': '中心词：{text}',
  'mindmate.diagramContext.field.topic': '主题：{text}',
  'mindmate.diagramContext.field.whole': '整体：{text}',
  'mindmate.diagramContext.field.event': '事件：{text}',
  'mindmate.diagramContext.field.process': '过程：{text}',
  'mindmate.diagramContext.field.focus': '焦点问题：{text}',
  'mindmate.diagramContext.field.dimension': '分类标准：{text}',
  'mindmate.diagramContext.field.braceDimension': '拆分标准：{text}',
  'mindmate.diagramContext.field.bridgeRelation': '类比关系：{text}',
  'mindmate.diagramContext.field.contexts': '联想：{items}',
  'mindmate.diagramContext.field.attributes': '特征：{items}',
  'mindmate.diagramContext.field.similarities': '相同点：{items}',
  'mindmate.diagramContext.field.diffs': '{name}的不同点：{items}',
  'mindmate.diagramContext.field.causes': '原因：{items}',
  'mindmate.diagramContext.field.effects': '结果：{items}',
  'mindmate.diagramContext.field.compare': '比较：{left} 与 {right}',
  'mindmate.diagramContext.field.analogy': '类比{n}：{left} 对 {right}',
  'mindmate.diagramContext.field.step': '步骤{n}：{text}',
  'mindmate.diagramContext.field.branch': '分支{n}：{text}',
  'mindmate.diagramContext.field.category': '类别{n}：{text}',
  'mindmate.diagramContext.field.part': '部分{n}：{text}',
  'mindmate.diagramContext.field.link': '{from} —{label}→ {to}',
  'mindmate.diagramContext.field.linkPlain': '{from} → {to}',
  'mindmate.diagramContext.field.linksHeading': '关系：',
}

function translate(key: string, params?: Record<string, unknown>): string {
  let text = zh[key] ?? key
  if (!params) return text
  for (const [name, value] of Object.entries(params)) {
    text = text.replaceAll(`{${name}}`, String(value ?? ''))
  }
  return text
}

function node(
  id: string,
  text: string,
  type: NodeType = 'branch',
  extra?: Partial<DiagramNode>
): DiagramNode {
  return { id, text, type, ...extra }
}

function edge(id: string, source: string, target: string, label?: string): Connection {
  return { id, source, target, label }
}

function brief(
  type: string,
  nodes: DiagramNode[],
  connections: Connection[] = [],
  focusQuestion?: string
): string {
  return buildMindmateDiagramBrief(type, nodes, connections, translate, focusQuestion)
}

describe('mindmate diagram brief', () => {
  it('numbers mind-map branches clockwise and keeps children with their branch', () => {
    const nodes = [
      node('topic', '中心主题', 'topic', { position: { x: 0, y: 100 } }),
      node('b1', '分支1', 'branch', { position: { x: 200, y: 40 } }),
      node('b2', '分支2', 'branch', { position: { x: 200, y: 140 } }),
      node('b3', '分支3', 'branch', { position: { x: -200, y: 140 } }),
      node('c31', '子项3.1', 'branch', { position: { x: -320, y: 100 }, textSecondary: 'gloss' }),
      node('c32', '子项3.2', 'branch', { position: { x: -320, y: 180 } }),
      node('b4', '分支4', 'branch', { position: { x: -200, y: 40 } }),
      node('c41', '子项4.1', 'branch', { position: { x: -320, y: 0 } }),
      node('c42', '子项4.2', 'branch', { position: { x: -320, y: 80 } }),
      node('smry:1', '总结', 'summary'),
    ]
    const connections = [
      edge('e1', 'topic', 'b1'),
      edge('e2', 'topic', 'b2'),
      edge('e3', 'topic', 'b3'),
      edge('e4', 'topic', 'b4'),
      edge('e5', 'b3', 'c31'),
      edge('e6', 'b3', 'c32'),
      edge('e7', 'b4', 'c41'),
      edge('e8', 'b4', 'c42'),
      edge('assoc', 'b1', 'b4'),
    ]
    connections[8].edgeType = 'association'
    expect(brief('mindmap', nodes, connections)).toBe(
      [
        '思维导图用来从一个中心主题向外分层展开。',
        '主题：中心主题',
        '分支1：分支1',
        '分支2：分支2',
        '分支3：分支3（子项3.1（gloss）、子项3.2）',
        '分支4：分支4（子项4.1、子项4.2）',
      ].join('\n')
    )
  })

  it('introduces a circle map by its central word and associations', () => {
    expect(
      brief('circle_map', [
        node('topic', '苹果', 'topic'),
        node('outer-boundary', '', 'boundary'),
        node('context-1', '红色', 'bubble'),
        node('context-0', '水果', 'bubble'),
        node('blank', '', 'bubble'),
      ])
    ).toBe(['圆圈图用来围绕一个中心词展开联想。', '中心词：苹果', '联想：水果、红色'].join('\n'))
  })

  it('describes bubble-map attributes in ring order', () => {
    expect(
      brief('bubble_map', [
        node('topic', '猫', 'topic'),
        node('bubble-1', '柔软', 'bubble'),
        node('bubble-0', '独立', 'bubble'),
      ])
    ).toBe(['气泡图用来描述一个事物的特征。', '主题：猫', '特征：独立、柔软'].join('\n'))
  })

  it('names both sides, shared points, and each side’s differences', () => {
    expect(
      brief('double_bubble_map', [
        node('left-topic', '猫', 'topic'),
        node('right-topic', '狗', 'topic'),
        node('similarity-0', '宠物', 'bubble'),
        node('left-diff-0', '独立', 'bubble'),
        node('right-diff-0', '忠诚', 'bubble'),
      ])
    ).toBe(
      [
        '双气泡图用来比较两个事物的相同点与不同点。',
        '比较：猫 与 狗',
        '相同点：宠物',
        '猫的不同点：独立',
        '狗的不同点：忠诚',
      ].join('\n')
    )
  })

  it('classifies a tree by its criterion and does not nest chained leaves', () => {
    expect(
      brief(
        'tree_map',
        [
          node('tree-topic', '动物', 'topic'),
          node('dimension-label', '按栖息地', 'label'),
          node('tree-cat-0', '陆地', 'branch'),
          node('tree-leaf-0-0', '猫', 'branch'),
          node('tree-leaf-0-1', '狗', 'branch'),
          node('tree-cat-1', '水里', 'branch'),
          node('tree-leaf-1-0', '鱼', 'branch'),
        ],
        [edge('chain', 'tree-leaf-0-0', 'tree-leaf-0-1')]
      )
    ).toBe(
      [
        '树形图用来按一个标准给事物分类。',
        '主题：动物',
        '分类标准：按栖息地',
        '类别1：陆地（猫、狗）',
        '类别2：水里（鱼）',
      ].join('\n')
    )
  })

  it('breaks a brace map into parts without treating the criterion as a part', () => {
    expect(
      brief(
        'brace_map',
        [
          node('brace-whole', '自行车', 'whole'),
          node('dimension-label', '按结构', 'label'),
          node('frame', '车架', 'brace'),
          node('wheel', '车轮', 'brace'),
          node('tire', '轮胎', 'brace'),
        ],
        [
          edge('p1', 'brace-whole', 'frame'),
          edge('p2', 'brace-whole', 'wheel'),
          edge('s1', 'wheel', 'tire'),
        ]
      )
    ).toBe(
      [
        '括号图用来把一个整体拆成它的组成部分。',
        '整体：自行车',
        '拆分标准：按结构',
        '部分1：车架',
        '部分2：车轮（轮胎）',
      ].join('\n')
    )
  })

  it('lists flow steps in order and keeps substeps on their step', () => {
    expect(
      brief(
        'flow_map',
        [
          node('flow-topic', '泡茶', 'topic'),
          node('flow-step-0', '烧水', 'flow'),
          node('flow-step-1', '冲泡', 'flow'),
          node('flow-substep-1-0', '倒水', 'flowSubstep'),
          node('flow-substep-1-1', '等待', 'flowSubstep'),
        ],
        [edge('chain', 'flow-step-0', 'flow-step-1')]
      )
    ).toBe(
      [
        '流程图用来按顺序列出一个过程的步骤。',
        '过程：泡茶',
        '步骤1：烧水',
        '步骤2：冲泡（倒水、等待）',
      ].join('\n')
    )
  })

  it('labels causes and effects of a multi-flow event', () => {
    expect(
      brief('multi_flow_map', [
        node('event', '迟到', 'event'),
        node('effect-0', '错过开头', 'branch'),
        node('cause-1', '堵车', 'branch'),
        node('cause-0', '起晚', 'branch'),
      ])
    ).toBe(
      [
        '复流程图用来分析一个事件的原因和结果。',
        '事件：迟到',
        '原因：起晚、堵车',
        '结果：错过开头',
      ].join('\n')
    )
  })

  it('states the bridge relationship and each analogy pair', () => {
    expect(
      brief('bridge_map', [
        node('dimension-label', '如同', 'label'),
        node('pair-1-right', '翅膀', 'branch'),
        node('pair-0-left', '鞋', 'branch'),
        node('pair-0-right', '脚', 'branch'),
        node('pair-1-left', '手套', 'branch'),
      ])
    ).toBe(
      [
        '桥形图用来用一组类比说明同一种关系。',
        '类比关系：如同',
        '类比1：鞋 对 脚',
        '类比2：手套 对 翅膀',
      ].join('\n')
    )
  })

  it('uses the focus question and relationship words on a concept map', () => {
    expect(
      brief(
        'concept_map',
        [
          node('topic', '水循环', 'topic'),
          node('sun', '太阳', 'branch'),
          node('vapor', '水蒸气', 'branch'),
        ],
        [edge('rel', 'sun', 'vapor', '加热'), edge('plain', 'topic', 'sun')],
        '水如何循环'
      )
    ).toBe(
      [
        '概念图用来把概念以及概念之间的关系组织成知识结构。',
        '焦点问题：水如何循环',
        '关系：',
        '太阳 —加热→ 水蒸气',
        '水循环 → 太阳',
      ].join('\n')
    )
  })

  it('keeps one copy of a repeated concept-map relationship', () => {
    expect(
      brief(
        'concept_map',
        [node('topic', '水', 'topic'), node('vapor', '水蒸气', 'branch')],
        [edge('a', 'topic', 'vapor', '蒸发为'), edge('b', 'topic', 'vapor', '蒸发为')]
      )
    ).toBe(
      [
        '概念图用来把概念以及概念之间的关系组织成知识结构。',
        '焦点问题：水',
        '关系：',
        '水 —蒸发为→ 水蒸气',
      ].join('\n')
    )
  })

  it('keeps tree leaves when the category label is empty', () => {
    expect(
      brief('tree_map', [
        node('tree-topic', '动物', 'topic'),
        node('tree-cat-0', '', 'branch'),
        node('tree-leaf-0-0', '猫', 'branch'),
        node('tree-leaf-0-1', '狗', 'branch'),
      ])
    ).toBe(['树形图用来按一个标准给事物分类。', '主题：动物', '类别1：猫、狗'].join('\n'))
  })

  it('keeps flow substeps when the step label is empty', () => {
    expect(
      brief('flow_map', [
        node('flow-topic', '泡茶', 'topic'),
        node('flow-step-0', '', 'flow'),
        node('flow-substep-0-0', '倒水', 'flowSubstep'),
      ])
    ).toBe(['流程图用来按顺序列出一个过程的步骤。', '过程：泡茶', '步骤1：倒水'].join('\n'))
  })

  it('stops when a brace part links back to itself', () => {
    expect(
      brief(
        'brace_map',
        [node('brace-whole', '自行车', 'whole'), node('wheel', '车轮', 'brace')],
        [edge('p', 'brace-whole', 'wheel'), edge('loop', 'wheel', 'wheel')]
      )
    ).toBe(['括号图用来把一个整体拆成它的组成部分。', '整体：自行车', '部分1：车轮'].join('\n'))
  })

  it('sends the outline with the prompt and shows only the prompt in the bubble', () => {
    const sent = withMindmateDiagramBrief(
      '请帮我看这张图',
      '思维导图用来从一个中心主题向外分层展开。'
    )
    expect(sent.startsWith('[MindMate diagram]')).toBe(true)
    expect(sent.endsWith('请帮我看这张图')).toBe(true)
    expect(displayMindmateUserQueryForUi(sent)).toBe('请帮我看这张图')
  })

  it('returns nothing when the canvas has no nodes', () => {
    expect(brief('mindmap', [])).toBe('')
  })
})
