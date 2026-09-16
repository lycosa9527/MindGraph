/**
 * Script-style canvas path: LLM-shaped specs (no node ids) → load →
 * add / delete / recalc, five rounds per Thinking Map.
 */
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  loadSpecForDiagramType,
  recalculateBraceMapLayout,
  recalculateBridgeMapLayout,
  recalculateBubbleMapLayout,
  recalculateCircleMapLayout,
  recalculateFlowMapLayout,
  recalculateMultiFlowMapLayout,
  recalculateTreeMapLayout,
} from '@/stores/specLoader'
import type { Connection, DiagramNode, DiagramType } from '@/types'
import {
  BRACE_WHOLE_NODE_ID,
  isLeftoverBraceMapId,
  takeBraceMapStableId,
} from '@/utils/braceMapIdentity'
import {
  isLeftoverBridgeMapId,
  stampBridgePairData,
  takeBridgeMapStableId,
} from '@/utils/bridgeMapIdentity'
import {
  BUBBLE_TOPIC_NODE_ID,
  isLeftoverBubbleMapId,
  stampBubbleAttributeData,
  takeBubbleMapStableId,
} from '@/utils/bubbleMapIdentity'
import {
  CIRCLE_MAP_UID_DATA_KEY,
  CIRCLE_TOPIC_NODE_ID,
  isCircleMapContextNode,
  isLeftoverCircleMapId,
  stampCircleContextData,
  takeCircleMapStableId,
} from '@/utils/circleMapIdentity'
import {
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
  isLeftoverDoubleBubbleId,
  readDoubleBubbleRole,
  takeDoubleBubbleMapStableId,
} from '@/utils/doubleBubbleMapIdentity'
import {
  FLOW_TOPIC_NODE_ID,
  isLeftoverFlowMapId,
  stampFlowMapStepData,
  takeFlowMapStableId,
} from '@/utils/flowMapIdentity'
import {
  MULTI_FLOW_EVENT_NODE_ID,
  MULTI_FLOW_UID_DATA_KEY,
  isLeftoverMultiFlowMapId,
  isMultiFlowCauseNode,
  stampMultiFlowData,
  takeMultiFlowMapStableId,
} from '@/utils/multiFlowMapIdentity'
import {
  TREE_MAP_UID_DATA_KEY,
  TREE_TOPIC_NODE_ID,
  isLeftoverTreeMapId,
  isTreeMapCategoryNode,
  stampTreeCategoryData,
  takeTreeMapStableId,
} from '@/utils/treeMapIdentity'

type Canvas = { nodes: DiagramNode[]; connections: Connection[] }

const ROUNDS = 5

const SPECS: Record<DiagramType, Record<string, unknown>[]> = {
  circle_map: [
    { topic: '水循环', context: ['蒸发', '凝结', '降水', '径流'] },
    { topic: '光合作用', context: ['叶绿体', '阳光', '水分', '氧气'] },
    { topic: '北京', context: ['故宫', '长城', '胡同', '烤鸭'] },
    { topic: '细胞', context: ['细胞核', '细胞膜', '细胞质', '线粒体'] },
    { topic: '牛顿', context: ['力学', '光学', '微积分', '万有引力'] },
  ],
  bubble_map: [
    { topic: '苹果', attributes: ['甜', '圆', '红', '脆'] },
    { topic: '大象', attributes: ['大', '灰', '长鼻', '群居'] },
    { topic: '太阳', attributes: ['热', '亮', '恒星', '圆形'] },
    { topic: '钢琴', attributes: ['键盘', '弦', '黑白', '音色'] },
    { topic: '长城', attributes: ['古老', '砖石', '绵长', '防御'] },
  ],
  double_bubble_map: [
    {
      left: '猫',
      right: '狗',
      similarities: ['宠物', '哺乳'],
      left_differences: ['独立', '夜行'],
      right_differences: ['忠诚', '群居'],
    },
    {
      left: '春',
      right: '夏',
      similarities: ['温暖', '生长'],
      left_differences: ['花开', '播种'],
      right_differences: ['炎热', '收获'],
    },
    {
      left: '城市',
      right: '农村',
      similarities: ['居住', '劳动'],
      left_differences: ['密集', '工业'],
      right_differences: ['开阔', '农业'],
    },
    {
      left: '小学',
      right: '中学',
      similarities: ['学校', '课程'],
      left_differences: ['启蒙', '游戏'],
      right_differences: ['学科', '考试'],
    },
    {
      left: '汽车',
      right: '火车',
      similarities: ['载人', '引擎'],
      left_differences: ['灵活', '公路'],
      right_differences: ['轨道', '运量'],
    },
  ],
  tree_map: [
    {
      topic: '动物',
      children: [
        { text: '哺乳', children: [{ text: '猫' }, { text: '狗' }] },
        { text: '鸟类', children: [{ text: '鹰' }, { text: '雀' }] },
      ],
    },
    {
      topic: '食物',
      children: [
        { text: '水果', children: [{ text: '苹果' }, { text: '梨' }] },
        { text: '蔬菜', children: [{ text: '白菜' }, { text: '萝卜' }] },
      ],
    },
    {
      topic: '中国',
      children: [
        { text: '北方', children: [{ text: '北京' }, { text: '天津' }] },
        { text: '南方', children: [{ text: '广州' }, { text: '深圳' }] },
      ],
    },
    {
      topic: '人体',
      children: [
        { text: '循环', children: [{ text: '心脏' }, { text: '血管' }] },
        { text: '呼吸', children: [{ text: '肺' }, { text: '气管' }] },
      ],
    },
    {
      topic: '文学',
      children: [
        { text: '诗歌', children: [{ text: '唐诗' }, { text: '宋词' }] },
        { text: '小说', children: [{ text: '短篇' }, { text: '长篇' }] },
      ],
    },
  ],
  brace_map: [
    {
      whole: '水分子',
      parts: [
        { name: '氢', subparts: [{ name: '质子' }, { name: '电子' }] },
        { name: '氧', subparts: [{ name: '核' }, { name: '电子云' }] },
      ],
    },
    {
      whole: '电脑',
      parts: [
        { name: '主机', subparts: [{ name: 'CPU' }, { name: '内存' }] },
        { name: '外设', subparts: [{ name: '键盘' }, { name: '鼠标' }] },
      ],
    },
    {
      whole: '学校',
      parts: [
        { name: '教学', subparts: [{ name: '教室' }, { name: '实验室' }] },
        { name: '后勤', subparts: [{ name: '食堂' }, { name: '宿舍' }] },
      ],
    },
    {
      whole: '汽车',
      parts: [
        { name: '动力', subparts: [{ name: '引擎' }, { name: '变速箱' }] },
        { name: '车身', subparts: [{ name: '底盘' }, { name: '车厢' }] },
      ],
    },
    {
      whole: '句子',
      parts: [
        { name: '主语', subparts: [{ name: '名词' }, { name: '代词' }] },
        { name: '谓语', subparts: [{ name: '动词' }, { name: '宾语' }] },
      ],
    },
  ],
  flow_map: [
    {
      title: '做饭',
      steps: ['洗菜', '切菜', '炒菜', '装盘'],
      substeps: [
        { step: '洗菜', substeps: ['冲洗', '沥干'] },
        { step: '切菜', substeps: ['切片', '切丝'] },
        { step: '炒菜', substeps: ['热锅', '翻炒'] },
        { step: '装盘', substeps: ['盛出', '摆盘'] },
      ],
    },
    {
      title: '申请护照',
      steps: ['准备材料', '预约', '递交', '领取'],
      substeps: [
        { step: '准备材料', substeps: ['照片', '户口'] },
        { step: '预约', substeps: ['网上', '确认'] },
        { step: '递交', substeps: ['窗口', '缴费'] },
        { step: '领取', substeps: ['通知', '签收'] },
      ],
    },
    {
      title: '种子发芽',
      steps: ['吸水', '破皮', '生根', '出芽'],
      substeps: [
        { step: '吸水', substeps: ['膨胀', '激活'] },
        { step: '破皮', substeps: ['裂开', '露出'] },
        { step: '生根', substeps: ['向下', '固着'] },
        { step: '出芽', substeps: ['向上', '见光'] },
      ],
    },
    {
      title: '水循环过程',
      steps: ['蒸发', '上升', '凝结', '降水'],
      substeps: [
        { step: '蒸发', substeps: ['受热', '汽化'] },
        { step: '上升', substeps: ['对流', '抬升'] },
        { step: '凝结', substeps: ['冷却', '成云'] },
        { step: '降水', substeps: ['雨', '雪'] },
      ],
    },
    {
      title: '光合作用过程',
      steps: ['吸光', '裂水', '固碳', '释氧'],
      substeps: [
        { step: '吸光', substeps: ['色素', '能量'] },
        { step: '裂水', substeps: ['分解', '电子'] },
        { step: '固碳', substeps: ['卡尔文', '糖'] },
        { step: '释氧', substeps: ['气孔', '扩散'] },
      ],
    },
  ],
  multi_flow_map: [
    { event: '战争', causes: ['领土', '资源', '同盟'], effects: ['伤亡', '重建', '条约'] },
    { event: '污染', causes: ['工业', '尾气', '垃圾'], effects: ['疾病', '气候', '生态'] },
    { event: '运动', causes: ['健康', '兴趣', '同伴'], effects: ['体能', '心情', '社交'] },
    { event: '考试', causes: ['复习', '作息', '心态'], effects: ['成绩', '自信', '规划'] },
    { event: '砍伐', causes: ['木材', '耕地', '开矿'], effects: ['水土流失', '栖息地', '碳汇'] },
  ],
  bridge_map: [
    {
      relating_factor: '比喻',
      analogies: [
        { left: '心脏', right: '水泵' },
        { left: '大脑', right: '电脑' },
      ],
    },
    {
      relating_factor: '功能',
      analogies: [
        { left: '根', right: '吸管' },
        { left: '叶', right: '工厂' },
      ],
    },
    {
      relating_factor: '结构',
      analogies: [
        { left: '骨', right: '梁' },
        { left: '血管', right: '管道' },
      ],
    },
    {
      relating_factor: '关系',
      analogies: [
        { left: '教师', right: '向导' },
        { left: '课本', right: '地图' },
      ],
    },
    {
      relating_factor: '过程',
      analogies: [
        { left: '记忆', right: '存档' },
        { left: '遗忘', right: '删除' },
      ],
    },
  ],
  concept_map: [],
  mindmap: [],
  mind_map: [],
}

const TYPES: DiagramType[] = [
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
]

function dummyDims(nodes: DiagramNode[]): Record<string, { width: number; height: number }> {
  const dims: Record<string, { width: number; height: number }> = {}
  for (const node of nodes) {
    dims[node.id] = { width: 120, height: 48 }
  }
  return dims
}

function nodeIds(nodes: DiagramNode[]): string[] {
  return nodes.map((node) => node.id).sort()
}

function isLeftover(type: DiagramType, nodeId: string): boolean {
  switch (type) {
    case 'circle_map':
      return isLeftoverCircleMapId(nodeId)
    case 'bubble_map':
      return isLeftoverBubbleMapId(nodeId)
    case 'double_bubble_map':
      return isLeftoverDoubleBubbleId(nodeId)
    case 'tree_map':
      return isLeftoverTreeMapId(nodeId)
    case 'brace_map':
      return isLeftoverBraceMapId(nodeId)
    case 'flow_map':
      return isLeftoverFlowMapId(nodeId)
    case 'multi_flow_map':
      return isLeftoverMultiFlowMapId(nodeId)
    case 'bridge_map':
      return isLeftoverBridgeMapId(nodeId)
    default:
      return false
  }
}

function assertCanvas(type: DiagramType, canvas: Canvas): void {
  expect(canvas.nodes.length).toBeGreaterThan(1)
  for (const node of canvas.nodes) {
    expect(Number.isFinite(node.position?.x)).toBe(true)
    expect(Number.isFinite(node.position?.y)).toBe(true)
    expect(isLeftover(type, node.id)).toBe(false)
  }
  const ids = new Set(canvas.nodes.map((node) => node.id))
  for (const connection of canvas.connections) {
    expect(ids.has(connection.source)).toBe(true)
    expect(ids.has(connection.target)).toBe(true)
  }
}

function recalc(type: DiagramType, canvas: Canvas): Canvas {
  const dims = dummyDims(canvas.nodes)
  if (type === 'circle_map') {
    return { ...canvas, nodes: recalculateCircleMapLayout(canvas.nodes, dims) }
  }
  if (type === 'bubble_map') {
    return { ...canvas, nodes: recalculateBubbleMapLayout(canvas.nodes, dims) }
  }
  if (type === 'tree_map') {
    return { ...canvas, nodes: recalculateTreeMapLayout(canvas.nodes, dims) }
  }
  if (type === 'brace_map') {
    return { ...canvas, nodes: recalculateBraceMapLayout(canvas.nodes, canvas.connections, dims) }
  }
  if (type === 'flow_map') {
    return { ...canvas, nodes: recalculateFlowMapLayout(canvas.nodes, dims) }
  }
  if (type === 'multi_flow_map') {
    return { ...canvas, nodes: recalculateMultiFlowMapLayout(canvas.nodes, null, {}, dims) }
  }
  if (type === 'bridge_map') {
    return { ...canvas, nodes: recalculateBridgeMapLayout(canvas.nodes, dims) }
  }
  return canvas
}

function claimed(nodes: DiagramNode[]): Set<string> {
  return new Set(nodes.map((node) => node.id))
}

function addNode(type: DiagramType, canvas: Canvas): Canvas {
  const ids = claimed(canvas.nodes)
  if (type === 'circle_map') {
    const nextId = takeCircleMapStableId(ids)
    const next: DiagramNode = {
      id: nextId,
      text: 'added',
      type: 'bubble',
      position: { x: 0, y: 0 },
      data: stampCircleContextData(
        canvas.nodes.filter((node) => isCircleMapContextNode(node)).length,
        { [CIRCLE_MAP_UID_DATA_KEY]: nextId }
      ),
    }
    return recalc(type, { ...canvas, nodes: [...canvas.nodes, next] })
  }
  if (type === 'bubble_map') {
    const nextId = takeBubbleMapStableId(ids)
    const next: DiagramNode = {
      id: nextId,
      text: 'added',
      type: 'bubble',
      position: { x: 0, y: 0 },
      data: stampBubbleAttributeData(canvas.nodes.length, { bubbleMapUid: nextId }),
    }
    return recalc(type, { ...canvas, nodes: [...canvas.nodes, next] })
  }
  if (type === 'double_bubble_map') {
    const sims = canvas.nodes
      .filter((node) => readDoubleBubbleRole(node) === 'similarity')
      .map((node) => ({ id: node.id, text: node.text }))
    sims.push({ id: takeDoubleBubbleMapStableId(ids), text: 'added' })
    const loaded = loadSpecForDiagramType(
      {
        left: canvas.nodes.find((node) => node.id === DOUBLE_BUBBLE_LEFT_TOPIC_ID)?.text,
        right: canvas.nodes.find((node) => node.id === DOUBLE_BUBBLE_RIGHT_TOPIC_ID)?.text,
        similarities: sims,
        left_differences: canvas.nodes
          .filter((node) => readDoubleBubbleRole(node) === 'leftDiff')
          .map((node) => ({ id: node.id, text: node.text })),
        right_differences: canvas.nodes
          .filter((node) => readDoubleBubbleRole(node) === 'rightDiff')
          .map((node) => ({ id: node.id, text: node.text })),
      },
      type
    )
    return { nodes: loaded.nodes, connections: loaded.connections }
  }
  if (type === 'tree_map') {
    const nextId = takeTreeMapStableId(ids)
    const cats = canvas.nodes.filter((node) => isTreeMapCategoryNode(node)).length
    const next: DiagramNode = {
      id: nextId,
      text: 'added',
      type: 'branch',
      position: { x: 0, y: 0 },
      data: stampTreeCategoryData(cats, { [TREE_MAP_UID_DATA_KEY]: nextId }),
    }
    return recalc(type, {
      nodes: [...canvas.nodes, next],
      connections: [
        ...canvas.connections,
        { id: `edge-${TREE_TOPIC_NODE_ID}-${nextId}`, source: TREE_TOPIC_NODE_ID, target: nextId },
      ],
    })
  }
  if (type === 'brace_map') {
    const nextId = takeBraceMapStableId(ids)
    const next: DiagramNode = {
      id: nextId,
      text: 'added',
      type: 'brace',
      position: { x: 0, y: 0 },
    }
    return recalc(type, {
      nodes: [...canvas.nodes, next],
      connections: [
        ...canvas.connections,
        {
          id: `edge-${BRACE_WHOLE_NODE_ID}-${nextId}`,
          source: BRACE_WHOLE_NODE_ID,
          target: nextId,
        },
      ],
    })
  }
  if (type === 'flow_map') {
    const nextId = takeFlowMapStableId(ids)
    const steps = canvas.nodes.filter((node) => node.type === 'flow').length
    const next: DiagramNode = {
      id: nextId,
      text: 'added',
      type: 'flow',
      position: { x: 200, y: 200 },
      data: stampFlowMapStepData(steps, { flowMapUid: nextId }),
    }
    return recalc(type, { ...canvas, nodes: [...canvas.nodes, next] })
  }
  if (type === 'multi_flow_map') {
    const nextId = takeMultiFlowMapStableId(ids)
    const causes = canvas.nodes.filter((node) => isMultiFlowCauseNode(node)).length
    const next: DiagramNode = {
      id: nextId,
      text: 'added',
      type: 'flow',
      position: { x: 0, y: 0 },
      data: stampMultiFlowData('cause', causes, { [MULTI_FLOW_UID_DATA_KEY]: nextId }),
    }
    return recalc(type, { ...canvas, nodes: [...canvas.nodes, next] })
  }
  const leftId = takeBridgeMapStableId(ids)
  const rightId = takeBridgeMapStableId(ids)
  const pairIndex =
    Math.max(
      0,
      ...canvas.nodes.map((node) =>
        typeof node.data?.pairIndex === 'number' ? node.data.pairIndex : -1
      )
    ) + 1
  const left: DiagramNode = {
    id: leftId,
    text: 'added-l',
    type: 'branch',
    position: { x: 0, y: 0 },
    data: stampBridgePairData(pairIndex, 'left', { bridgeMapUid: leftId }),
  }
  const right: DiagramNode = {
    id: rightId,
    text: 'added-r',
    type: 'branch',
    position: { x: 0, y: 0 },
    data: stampBridgePairData(pairIndex, 'right', { bridgeMapUid: rightId }),
  }
  return recalc(type, { ...canvas, nodes: [...canvas.nodes, left, right] })
}

function removableId(type: DiagramType, canvas: Canvas): string | undefined {
  const reserved = new Set([
    CIRCLE_TOPIC_NODE_ID,
    'outer-boundary',
    BUBBLE_TOPIC_NODE_ID,
    DOUBLE_BUBBLE_LEFT_TOPIC_ID,
    DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
    TREE_TOPIC_NODE_ID,
    BRACE_WHOLE_NODE_ID,
    FLOW_TOPIC_NODE_ID,
    MULTI_FLOW_EVENT_NODE_ID,
    'dimension-label',
  ])
  return [...canvas.nodes].reverse().find((node) => !reserved.has(node.id))?.id
}

function deleteNode(type: DiagramType, canvas: Canvas): Canvas {
  const target = removableId(type, canvas)
  if (!target) return canvas
  const remove = new Set<string>([target])
  if (type === 'bridge_map') {
    const node = canvas.nodes.find((row) => row.id === target)
    const pairIndex = typeof node?.data?.pairIndex === 'number' ? node.data.pairIndex : -1
    for (const row of canvas.nodes) {
      if (typeof row.data?.pairIndex === 'number' && row.data.pairIndex === pairIndex) {
        remove.add(row.id)
      }
    }
  }
  const nodes = canvas.nodes.filter((node) => !remove.has(node.id))
  const connections = canvas.connections.filter(
    (connection) => !remove.has(connection.source) && !remove.has(connection.target)
  )
  if (type === 'double_bubble_map') {
    const loaded = loadSpecForDiagramType(
      {
        left: nodes.find((node) => node.id === DOUBLE_BUBBLE_LEFT_TOPIC_ID)?.text,
        right: nodes.find((node) => node.id === DOUBLE_BUBBLE_RIGHT_TOPIC_ID)?.text,
        similarities: nodes
          .filter((node) => readDoubleBubbleRole(node) === 'similarity')
          .map((node) => ({ id: node.id, text: node.text })),
        left_differences: nodes
          .filter((node) => readDoubleBubbleRole(node) === 'leftDiff')
          .map((node) => ({ id: node.id, text: node.text })),
        right_differences: nodes
          .filter((node) => readDoubleBubbleRole(node) === 'rightDiff')
          .map((node) => ({ id: node.id, text: node.text })),
      },
      type
    )
    return { nodes: loaded.nodes, connections: loaded.connections }
  }
  return recalc(type, { nodes, connections })
}

function exerciseCanvas(type: DiagramType, spec: unknown): void {
  const loaded = loadSpecForDiagramType(spec, type)
  let canvas: Canvas = { nodes: loaded.nodes, connections: loaded.connections }
  assertCanvas(type, canvas)

  const afterLoadIds = nodeIds(canvas.nodes)
  canvas = recalc(type, canvas)
  expect(nodeIds(canvas.nodes)).toEqual(afterLoadIds)
  assertCanvas(type, canvas)

  const beforeAdd = new Set(canvas.nodes.map((node) => node.id))
  canvas = addNode(type, canvas)
  const added = canvas.nodes.filter((node) => !beforeAdd.has(node.id))
  expect(added.length).toBeGreaterThan(0)
  expect(added.every((node) => !isLeftover(type, node.id))).toBe(true)
  expect([...beforeAdd].every((id) => canvas.nodes.some((node) => node.id === id))).toBe(true)
  assertCanvas(type, canvas)

  const beforeDelete = new Set(canvas.nodes.map((node) => node.id))
  const removeId = removableId(type, canvas)
  const removedPair =
    type === 'bridge_map'
      ? canvas.nodes
          .filter((node) => {
            const target = canvas.nodes.find((row) => row.id === removeId)
            return (
              typeof node.data?.pairIndex === 'number' &&
              node.data.pairIndex === target?.data?.pairIndex
            )
          })
          .map((node) => node.id)
      : removeId
        ? [removeId]
        : []
  canvas = deleteNode(type, canvas)
  if (removedPair.length > 0) {
    expect(removedPair.every((id) => canvas.nodes.every((node) => node.id !== id))).toBe(true)
    expect(
      [...beforeDelete]
        .filter((id) => !removedPair.includes(id))
        .every((id) => canvas.nodes.some((node) => node.id === id))
    ).toBe(true)
  }
  canvas = recalc(type, canvas)
  assertCanvas(type, canvas)
}

const LIVE_REPORT = resolve(__dirname, '../../tmp/thinking_maps_autocomplete_live/report.json')

describe.each(TYPES)('%s autocomplete load / add / delete / recalc × 5', (type) => {
  it('keeps UUIDs and finite layout across five LLM-shaped rounds', () => {
    const specs = SPECS[type]
    expect(specs).toHaveLength(ROUNDS)
    for (const spec of specs) {
      exerciseCanvas(type, spec)
    }
  })
})

describe.skipIf(!existsSync(LIVE_REPORT))('live LLM autocomplete specs', () => {
  it('loads 40 live specs then add/delete/recalc', () => {
    const report = JSON.parse(readFileSync(LIVE_REPORT, 'utf8')) as {
      results: Array<{ diagram_type: DiagramType; spec_json: string }>
    }
    expect(report.results).toHaveLength(40)
    for (const row of report.results) {
      const spec = JSON.parse(readFileSync(resolve(__dirname, '../..', row.spec_json), 'utf8'))
      exerciseCanvas(row.diagram_type, spec)
    }
  })
})
