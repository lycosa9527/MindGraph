import { describe, expect, it } from 'vitest'

import { DEFAULT_CENTER_Y } from '@/composables/diagrams/layoutConfig'
import { loadBridgeMapSpec, recalculateBridgeMapLayout } from '@/stores/specLoader/bridgeMap'
import type { DiagramNode } from '@/types'
import { measureBridgeDimensionLabelBox } from '@/utils/bridgeMapLabelLayout'
import { bridgePairContentBox } from '@/utils/bridgeMapPairBox'
import {
  BRIDGE_TURN_OUTSET_PX,
  bridgePairSlot,
  bridgeSerpentineInk,
  openBridgeSeparatorGaps,
} from '@/utils/bridgeMapSerpentine'

function upper(nodes: DiagramNode[], text: string): DiagramNode {
  const found = nodes.find((node) => node.text === text && node.data?.position === 'left')
  if (!found?.position) throw new Error(`missing ${text}`)
  return found
}

function analogies(count: number, gloss = false) {
  return Array.from({ length: count }, (_, index) => ({
    left: `上${index + 1}`,
    right: `下${index + 1}`,
    ...(gloss
      ? {
          left_secondary: `Upper ${index + 1}`,
          right_secondary:
            index === 4
              ? 'A long English gloss that wraps inside the lower word'
              : `Lower ${index + 1}`,
        }
      : {}),
  }))
}

function boxes(nodes: DiagramNode[]) {
  return nodes
    .filter((node) => node.position && (node.type === 'branch' || node.type === 'label'))
    .map((node) => {
      const box =
        node.id === 'dimension-label'
          ? measureBridgeDimensionLabelBox(node.text ?? '', node.textSecondary)
          : bridgePairContentBox(node.text ?? '', node.textSecondary)
      return {
        label: `${node.data?.position ?? node.type}:${node.text}`,
        x: node.position?.x ?? 0,
        y: node.position?.y ?? 0,
        w: box.width,
        h: box.height,
      }
    })
}

function overlaps(nodes: DiagramNode[]): string[] {
  const painted = boxes(nodes)
  const hits: string[] = []
  for (let left = 0; left < painted.length; left += 1) {
    for (let right = left + 1; right < painted.length; right += 1) {
      const a = painted[left]
      const b = painted[right]
      const gapX = Math.max(a.x, b.x) - Math.min(a.x + a.w, b.x + b.w)
      const gapY = Math.max(a.y, b.y) - Math.min(a.y + a.h, b.y + b.h)
      if (gapX < -1 && gapY < -1) {
        hits.push(`${a.label} ∩ ${b.label} (x ${gapX.toFixed(0)}px, y ${gapY.toFixed(0)}px)`)
      }
    }
  }
  return hits
}

describe('bridge map serpentine', () => {
  it('keeps five pairs on one bridge', () => {
    const loaded = loadBridgeMapSpec({
      dimension: '如同',
      analogies: analogies(5),
    })
    const first = upper(loaded.nodes, '上1')
    const fifth = upper(loaded.nodes, '上5')
    expect(fifth.position?.x ?? 0).toBeGreaterThan(first.position?.x ?? 0)
    expect(fifth.position?.y).toBeCloseTo(first.position?.y ?? 0, 4)
    const ink = bridgeSerpentineInk(
      [0, 1, 2, 3, 4].map((index) => ({
        pairIndex: index,
        upper: { x: index * 80, y: 40, width: 40, height: 36 },
        lower: { x: index * 80, y: 90, width: 40, height: 36 },
      }))
    )
    expect(ink.lines).toHaveLength(1)
    expect(ink.lines.some((line) => line.x1 === line.x2)).toBe(false)
    expect(ink.along).toHaveLength(4)
  })

  it('U-turns the sixth pair under the fifth and walks back', () => {
    const loaded = loadBridgeMapSpec({
      dimension: '如同',
      analogies: analogies(7),
    })
    const laid = recalculateBridgeMapLayout(loaded.nodes, {})
    const fifth = upper(laid, '上5')
    const sixth = upper(laid, '上6')
    const seventh = upper(laid, '上7')
    expect(sixth.position?.y ?? 0).toBeGreaterThan((fifth.position?.y ?? 0) + 36)
    expect(sixth.position?.x).toBeCloseTo(fifth.position?.x ?? 0, 4)
    expect(seventh.position?.y).toBeCloseTo(sixth.position?.y ?? 0, 4)
    expect(seventh.position?.x ?? 0).toBeLessThan(sixth.position?.x ?? 0)
    expect(bridgePairSlot(9)).toEqual({ row: 1, column: 0, direction: 'rtl' })
    expect(bridgePairSlot(10)).toEqual({ row: 2, column: 0, direction: 'ltr' })
  })

  it('draws the bridge down at the turn and keeps as-marks on each row', () => {
    const row = (index: number, x: number, y: number) => ({
      pairIndex: index,
      upper: { x, y, width: 50, height: 36 },
      lower: { x, y: y + 50, width: 50, height: 36 },
    })
    const ink = bridgeSerpentineInk([
      row(0, 0, 0),
      row(1, 100, 0),
      row(2, 200, 0),
      row(3, 300, 0),
      row(4, 400, 0),
      row(5, 400, 160),
      row(6, 300, 160),
    ])
    const vertical = ink.lines.find((line) => line.x1 === line.x2)
    expect(vertical?.x1).toBe(450 + BRIDGE_TURN_OUTSET_PX)
    expect(vertical?.y1).toBeLessThan(vertical?.y2 ?? 0)
    expect(ink.along.map((marker) => marker.pairIndex)).toEqual([0, 1, 2, 3, 5])
    expect(ink.lines.filter((line) => line.x1 === line.x2)).toHaveLength(1)
  })

  it('stops the bridge stroke at each separator', () => {
    const opened = openBridgeSeparatorGaps(
      [{ x1: 0, y1: 10, x2: 200, y2: 10 }],
      [
        { x: 80, y: 10 },
        { x: 140, y: 10 },
      ],
      12
    )
    expect(opened).toEqual([
      { x1: 0, y1: 10, x2: 74, y2: 10 },
      { x1: 86, y1: 10, x2: 134, y2: 10 },
      { x1: 146, y1: 10, x2: 200, y2: 10 },
    ])
    const drop = { x1: 495, y1: 10, x2: 495, y2: 80 }
    expect(openBridgeSeparatorGaps([drop], [{ x: 495, y: 40 }], 12)).toEqual([drop])
  })

  it('clears bilingual pairs, including a long gloss on the turn', () => {
    const loaded = loadBridgeMapSpec({
      dimension: '如同',
      dimension_secondary: 'As a kind of',
      analogies: analogies(8, true),
    })
    const laid = recalculateBridgeMapLayout(loaded.nodes, {})
    expect(overlaps(laid)).toEqual([])
    const fifthLower = laid.find((node) => node.text === '下5')
    const sixthUpper = upper(laid, '上6')
    expect(sixthUpper.position?.y ?? 0).toBeGreaterThan(
      (fifthLower?.position?.y ?? 0) + bridgePairContentBox('下5', fifthLower?.textSecondary).height
    )
    const label = laid.find((node) => node.id === 'dimension-label')
    expect((label?.position?.y ?? 0) + 1).toBeLessThan(DEFAULT_CENTER_Y)
  })
})
