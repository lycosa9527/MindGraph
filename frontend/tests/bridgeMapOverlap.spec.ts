/**
 * Painted boxes for wrapped bridge maps, including a second language.
 * A hit means two words share area.
 */
import { describe, expect, it } from 'vitest'

import { loadBridgeMapSpec, recalculateBridgeMapLayout } from '@/stores/specLoader/bridgeMap'
import type { DiagramNode } from '@/types'
import { isBridgeMapPairNode, readBridgePairIndex } from '@/utils/bridgeMapIdentity'
import { measureBridgeDimensionLabelBox } from '@/utils/bridgeMapLabelLayout'
import { bridgePairContentBox, bridgeSectionRight } from '@/utils/bridgeMapPairBox'
import {
  BRIDGE_PAIRS_PER_ROW,
  BRIDGE_TURN_OUTSET_PX,
  bridgeSerpentineInk,
} from '@/utils/bridgeMapSerpentine'

const LONG = '选择基础模型并完成对比评估说明文字用来检查换行'
const GLOSS = 'Compare the base models and write down what changed after this line wraps'

interface Analogy {
  left: string
  right: string
  left_secondary?: string
  right_secondary?: string
}

interface Box {
  id: string
  label: string
  x: number
  y: number
  w: number
  h: number
}

function pair(index: number, left = `上${index + 1}`, right = `下${index + 1}`): Analogy {
  return { left, right }
}

function glossed(index: number, long = false): Analogy {
  return {
    left: long ? LONG : `上${index + 1}`,
    right: long ? `${LONG}下` : `下${index + 1}`,
    left_secondary: long ? GLOSS : `Upper ${index + 1}`,
    right_secondary: long ? `${GLOSS} lower` : `Lower ${index + 1}`,
  }
}

function contentBox(node: DiagramNode): { width: number; height: number } {
  if (node.id === 'dimension-label') {
    return measureBridgeDimensionLabelBox(node.text ?? '', node.textSecondary)
  }
  return bridgePairContentBox(node.text ?? '', node.textSecondary, node.style?.fontSize)
}

function painted(
  nodes: DiagramNode[],
  override: Record<string, { width: number; height: number }> = {}
): Box[] {
  return nodes
    .filter((node) => node.position && (node.type === 'branch' || node.type === 'label'))
    .map((node) => {
      const box = override[node.id] ?? contentBox(node)
      return {
        id: node.id,
        label: `${node.data?.position ?? node.type}:${node.text}`,
        x: node.position?.x ?? 0,
        y: node.position?.y ?? 0,
        w: box.width,
        h: box.height,
      }
    })
}

function overlapReport(
  nodes: DiagramNode[],
  override: Record<string, { width: number; height: number }> = {}
): string[] {
  const boxes = painted(nodes, override)
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

function laidOut(analogies: Analogy[], dimension = '如同', dimensionSecondary = ''): DiagramNode[] {
  const loaded = loadBridgeMapSpec({
    dimension,
    ...(dimensionSecondary ? { dimension_secondary: dimensionSecondary } : {}),
    analogies,
  })
  return recalculateBridgeMapLayout(loaded.nodes, {})
}

function side(nodes: DiagramNode[], text: string, position: 'left' | 'right'): DiagramNode {
  const found = nodes.find((node) => node.text === text && node.data?.position === position)
  if (!found?.position) throw new Error(`missing ${position} ${text}`)
  return found
}

const CASES: Array<{ title: string; nodes: () => DiagramNode[] }> = [
  {
    title: '六个短配对',
    nodes: () => laidOut(Array.from({ length: 6 }, (_, index) => pair(index))),
  },
  {
    title: '七个短配对',
    nodes: () => laidOut(Array.from({ length: 7 }, (_, index) => pair(index))),
  },
  {
    title: '十二个短配对',
    nodes: () => laidOut(Array.from({ length: 12 }, (_, index) => pair(index))),
  },
  {
    title: '转弯处的主文字换行',
    nodes: () =>
      laidOut([
        pair(0, '猫', '喵'),
        pair(1, '狗', '汪'),
        pair(2, '鸟', '啾'),
        pair(3, '鱼', '游'),
        pair(4, LONG, `${LONG}对照`),
        pair(5, '下一步', '下一对'),
        pair(6, LONG, '短'),
      ]),
  },
  {
    title: '下一行比上一行更宽',
    nodes: () =>
      laidOut([
        pair(0, '甲', '乙'),
        pair(1, '丙', '丁'),
        pair(2, '戊', '己'),
        pair(3, '庚', '辛'),
        pair(4, '短', '短'),
        pair(5, LONG, `${LONG}更宽的下词`),
        pair(6, '回', '来'),
      ]),
  },
  {
    title: '双语短句',
    nodes: () =>
      laidOut(
        Array.from({ length: 8 }, (_, index) => glossed(index)),
        '关系',
        'Relationship'
      ),
  },
  {
    title: '双语换行',
    nodes: () =>
      laidOut(
        Array.from({ length: 8 }, (_, index) => glossed(index, index % 5 === 4 || index === 5)),
        '关系',
        'A relationship long enough to wrap beside the first pair'
      ),
  },
  {
    title: '只有部分配对有译文',
    nodes: () =>
      laidOut(
        Array.from({ length: 7 }, (_, index) =>
          index === 2 || index === 4 ? glossed(index, true) : pair(index)
        ),
        '如同',
        'As'
      ),
  },
  {
    title: '长关系名加七对双语',
    nodes: () =>
      laidOut(
        Array.from({ length: 7 }, (_, index) => glossed(index, index === 4)),
        '中国古典文学名著中的人物对照关系说明',
        'Characters compared across classical Chinese novels'
      ),
  },
]

describe('bridge map overlap', () => {
  it.each(CASES)('$title stays clear', ({ nodes }) => {
    expect(overlapReport(nodes())).toEqual([])
  })

  it('drops the second row below a wrapped bilingual word on the turn', () => {
    const nodes = laidOut(
      Array.from({ length: 6 }, (_, index) => glossed(index, index === 4)),
      '关系',
      'Relationship'
    )
    const lower = side(nodes, glossed(4, true).right, 'right')
    const next = side(nodes, glossed(5, false).left, 'left')
    const lowerBox = bridgePairContentBox(lower.text ?? '', lower.textSecondary)
    expect(lowerBox.height).toBeGreaterThan(36)
    expect(lowerBox.width).toBeGreaterThan(80)
    expect(next.position?.y ?? 0).toBeGreaterThan((lower.position?.y ?? 0) + lowerBox.height)
    expect(overlapReport(nodes)).toEqual([])
  })

  it('turns left on the third row without crossing the first column', () => {
    const nodes = laidOut(Array.from({ length: 12 }, (_, index) => glossed(index, index === 9)))
    const tenth = side(nodes, glossed(9, true).left, 'left')
    const eleventh = side(nodes, glossed(10, false).left, 'left')
    expect(eleventh.position?.y ?? 0).toBeGreaterThan(tenth.position?.y ?? 0)
    expect(eleventh.position?.x).toBeCloseTo(tenth.position?.x ?? 0, 4)
    const byIndex = new Map<number, { upper: DiagramNode; lower: DiagramNode }>()
    for (const node of nodes) {
      if (!isBridgeMapPairNode(node) || !node.position) continue
      const index = readBridgePairIndex(node)
      const entry = byIndex.get(index) ?? { upper: node, lower: node }
      if (node.data?.position === 'left') entry.upper = node
      if (node.data?.position === 'right') entry.lower = node
      byIndex.set(index, entry)
    }
    const ink = bridgeSerpentineInk(
      [...byIndex.entries()].map(([pairIndex, entry]) => {
        const upperBox = contentBox(entry.upper)
        const lowerBox = contentBox(entry.lower)
        return {
          pairIndex,
          upper: {
            x: entry.upper.position?.x ?? 0,
            y: entry.upper.position?.y ?? 0,
            width: upperBox.width,
            height: upperBox.height,
          },
          lower: {
            x: entry.lower.position?.x ?? 0,
            y: entry.lower.position?.y ?? 0,
            width: lowerBox.width,
            height: lowerBox.height,
          },
        }
      })
    )
    const verticals = ink.lines
      .filter((line) => line.x1 === line.x2)
      .sort((left, right) => left.x1 - right.x1)
    expect(verticals).toHaveLength(2)
    const first = side(nodes, glossed(0, false).left, 'left')
    expect(verticals[0]?.x1).toBeCloseTo((first.position?.x ?? 0) - BRIDGE_TURN_OUTSET_PX, 4)
    expect(verticals[1]?.x1 ?? 0).toBeGreaterThan(verticals[0]?.x1 ?? 0)
    for (const marker of ink.along) {
      const current = byIndex.get(marker.pairIndex)
      const following = byIndex.get(marker.pairIndex + 1)
      if (!current || !following) continue
      const currentLeft = Math.min(current.upper.position?.x ?? 0, current.lower.position?.x ?? 0)
      const followingLeft = Math.min(
        following.upper.position?.x ?? 0,
        following.lower.position?.x ?? 0
      )
      const currentRight = bridgeSectionRight(
        current.upper.position?.x ?? 0,
        contentBox(current.upper).width,
        current.lower.position?.x ?? 0,
        contentBox(current.lower).width
      )
      const followingRight = bridgeSectionRight(
        following.upper.position?.x ?? 0,
        contentBox(following.upper).width,
        following.lower.position?.x ?? 0,
        contentBox(following.lower).width
      )
      const gapStart = currentLeft <= followingLeft ? currentRight : followingRight
      const gapEnd = currentLeft <= followingLeft ? followingLeft : currentLeft
      expect(marker.x).toBeGreaterThan(gapStart)
      expect(marker.x).toBeLessThan(gapEnd)
    }
    expect(overlapReport(nodes)).toEqual([])
  })

  it('opens the bridge gap when a pair has a shape', () => {
    const loaded = loadBridgeMapSpec({
      dimension: '如同',
      analogies: Array.from({ length: 6 }, (_, index) => glossed(index, index === 4)),
    })
    const shaped = loaded.nodes.map((node) =>
      isBridgeMapPairNode(node)
        ? { ...node, style: { ...(node.style ?? {}), nodeShape: 'rounded' as const } }
        : node
    )
    const laid = recalculateBridgeMapLayout(shaped, {})
    const upper = side(laid, glossed(0, false).left, 'left')
    const lower = side(laid, glossed(0, false).right, 'right')
    const upperBottom = (upper.position?.y ?? 0) + contentBox(upper).height
    expect(lower.position?.y ?? 0).toBeGreaterThanOrEqual(upperBottom + 16 - 0.5)
    expect(overlapReport(laid)).toEqual([])
  })

  it('keeps a measured box that is larger than the estimate from colliding', () => {
    const loaded = loadBridgeMapSpec({
      dimension: '如同',
      dimension_secondary: 'As',
      analogies: Array.from({ length: 7 }, (_, index) =>
        glossed(index, index === 4 || index === 5)
      ),
    })
    const override = Object.fromEntries(
      loaded.nodes.map((node) => {
        const box = contentBox(node)
        return [node.id, { width: box.width + 28, height: box.height + 20 }]
      })
    )
    const laid = recalculateBridgeMapLayout(loaded.nodes, override)
    expect(overlapReport(laid, override)).toEqual([])
  })

  it('wraps by reading order when a pair index is missing', () => {
    const loaded = loadBridgeMapSpec({
      dimension: '如同',
      analogies: Array.from({ length: 8 }, (_, index) => pair(index)),
    })
    const kept = loaded.nodes.filter((node) => readBridgePairIndex(node) !== 2)
    const laid = recalculateBridgeMapLayout(kept, {})
    const fifth = side(laid, '上6', 'left')
    const sixth = side(laid, '上7', 'left')
    expect(sixth.position?.y ?? 0).toBeGreaterThan(fifth.position?.y ?? 0)
    expect(sixth.position?.x).toBeCloseTo(fifth.position?.x ?? 0, 4)
    expect(overlapReport(laid)).toEqual([])
    expect(BRIDGE_PAIRS_PER_ROW).toBe(5)
  })
})
