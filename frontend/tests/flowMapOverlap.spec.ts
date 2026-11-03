/**
 * Painted boxes for wrapped flow maps. A hit means two pills share area.
 */
import { describe, expect, it } from 'vitest'

import { attachRemainingSecondary } from '@/diagramBilingual/attachRest'
import { offsetFlowLayoutForSecondary } from '@/diagramBilingual/flowLayout'
import { loadFlowMapSpec, recalculateFlowMapLayout } from '@/stores/specLoader/flowMap'
import type { DiagramNode } from '@/types'
import {
  type FlowPillRole,
  flowSecondaryExtraHeight,
  measureFlowRolePill,
} from '@/utils/flowPillBox'

interface FlowCase {
  title: string
  steps: string[]
  substeps?: Array<{ step: string; substeps: string[] }>
  secondary?: Record<string, unknown>
}

function roleOf(node: DiagramNode): FlowPillRole {
  if (node.type === 'flowSubstep') return 'substep'
  if (node.type === 'flow') return 'step'
  return 'topic'
}

/** Border box the pill would paint, including a wrapped second language. */
function paintedBox(node: DiagramNode): { width: number; height: number } {
  const role = roleOf(node)
  const box = measureFlowRolePill(node.text ?? '', role)
  return {
    width: box.boxWidth,
    height: box.boxHeight + flowSecondaryExtraHeight(node.text ?? '', node.textSecondary, role),
  }
}

function prepare(spec: FlowCase): DiagramNode[] {
  const loaded = loadFlowMapSpec({
    title: spec.title,
    orientation: 'horizontal',
    steps: spec.steps,
    substeps: spec.substeps ?? [],
    ...(spec.secondary ? { secondary: spec.secondary } : {}),
  })
  attachRemainingSecondary('flow_map', loaded.nodes, {
    title: spec.title,
    steps: spec.steps,
    substeps: spec.substeps ?? [],
    ...(spec.secondary ? { secondary: spec.secondary } : {}),
  })
  return offsetFlowLayoutForSecondary(loaded.nodes)
}

function measuredLayout(nodes: DiagramNode[]): DiagramNode[] {
  const dims = Object.fromEntries(nodes.map((node) => [node.id, paintedBox(node)]))
  return recalculateFlowMapLayout(nodes, dims)
}

function overlapReport(nodes: DiagramNode[]): string[] {
  const boxes = nodes
    .filter(
      (node) =>
        node.position &&
        (node.type === 'topic' || node.type === 'flow' || node.type === 'flowSubstep')
    )
    .map((node) => {
      const box = paintedBox(node)
      return {
        label: `${node.type}:${node.text}`,
        x: node.position?.x ?? 0,
        y: node.position?.y ?? 0,
        w: box.width,
        h: box.height,
      }
    })
  const hits: string[] = []
  for (let left = 0; left < boxes.length; left += 1) {
    for (let right = left + 1; right < boxes.length; right += 1) {
      const a = boxes[left]
      const b = boxes[right]
      const gapX = Math.max(a.x, b.x) - Math.min(a.x + a.w, b.x + b.w)
      const gapY = Math.max(a.y, b.y) - Math.min(a.y + a.h, b.y + b.h)
      if (gapX < -1 && gapY < -1) {
        hits.push(`${a.label} ∩ ${b.label} (x ${gapX.toFixed(0)}px, y ${gapY.toFixed(0)}px)`)
      }
    }
  }
  return hits
}

const LONG = '选择基础模型并完成对比评估说明文字'
const GLOSS = 'Compare the base models and write down what changed'

const CASES: FlowCase[] = [
  {
    title: '短流程',
    steps: ['准备', '加热', '搅拌', '装盘', '品尝', '清洗'],
  },
  {
    title: '七步',
    steps: ['一', '二', '三', '四', '五', '六', '七'],
  },
  {
    title: '三行',
    steps: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'],
  },
  {
    title: '转弯处换行',
    steps: ['取水', '过滤', LONG, '静置', '分装', '冷藏', '饮用'],
  },
  {
    title: '每步都有子步骤',
    steps: ['买菜', '洗切', '热锅', '翻炒', '调味', '出锅', '装盘', '打扫'],
    substeps: [
      { step: '买菜', substeps: ['列清单', '比价格'] },
      { step: '洗切', substeps: ['冲洗', '切丝'] },
      { step: '热锅', substeps: ['倒油'] },
      { step: '翻炒', substeps: ['先蒜', '再菜', '最后肉'] },
      { step: '调味', substeps: ['盐', '酱油'] },
      { step: '出锅', substeps: ['关火'] },
      { step: '装盘', substeps: ['垫叶', '摆盘'] },
      { step: '打扫', substeps: ['洗碗', '擦桌子'] },
    ],
  },
  {
    title: '拐角堆了四条子步骤',
    steps: ['A', 'B', 'C', 'D', '汇总', '下一步'],
    substeps: [{ step: '汇总', substeps: ['甲', '乙', '丙', '丁'] }],
  },
  {
    title: '双语短句',
    steps: ['准备', '加热', '搅拌', '装盘', '品尝', '清洗', '收纳'],
    secondary: {
      title: 'Weeknight noodles',
      steps: ['Prep', 'Heat', 'Stir', 'Plate', 'Taste', 'Wash', 'Store'],
    },
  },
  {
    title: '双语长注释',
    steps: ['取水', '过滤', '煮沸', '静置', '分装', '冷藏', '饮用', '记录'],
    secondary: {
      title: 'Boil and cool drinking water',
      steps: [
        'Draw cold water',
        GLOSS,
        'Bring it to a rolling boil',
        'Let it stand until safe to handle',
        'Pour into clean bottles',
        'Refrigerate overnight',
        'Drink within two days',
        'Note the date on the bottle',
      ],
    },
  },
  {
    title: '双语带子步骤',
    steps: ['买菜', '洗切', '热锅', '翻炒', '调味', '出锅', '装盘'],
    substeps: [
      { step: '洗切', substeps: ['冲洗', '切丝'] },
      { step: '翻炒', substeps: ['先蒜', '再菜', LONG] },
      { step: '装盘', substeps: ['垫叶', '摆盘'] },
    ],
    secondary: {
      title: 'Stir fry',
      steps: ['Shop', 'Wash and cut', 'Heat the pan', 'Stir fry', 'Season', 'Take it off', 'Plate'],
      substeps: [
        { substeps: [] },
        { substeps: ['Rinse', 'Slice thinly'] },
        { substeps: [] },
        { substeps: ['Garlic first', 'Vegetables next', GLOSS] },
        { substeps: [] },
        { substeps: [] },
        { substeps: ['Leaves', 'Arrange'] },
      ],
    },
  },
  {
    title: '双语三行',
    steps: Array.from({ length: 12 }, (_, index) => `步骤${index + 1}`),
    secondary: {
      title: 'Twelve step process',
      steps: Array.from(
        { length: 12 },
        (_, index) => `Step ${index + 1}: ${index % 5 === 4 ? GLOSS : 'Continue'}`
      ),
    },
  },
]

describe('flow map serpentine overlap', () => {
  it.each(CASES)('$title stays clear after measurement', (spec) => {
    const laidOut = measuredLayout(prepare(spec))
    expect(overlapReport(laidOut)).toEqual([])
  })

  it.each(CASES)('$title stays clear before the browser measures', (spec) => {
    expect(overlapReport(prepare(spec))).toEqual([])
  })
})
