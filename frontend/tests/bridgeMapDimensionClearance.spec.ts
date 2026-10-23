/**
 * Bridge-map dimension labels wrap, and the first pair starts after that box.
 */
import { describe, expect, it } from 'vitest'

import { DEFAULT_CENTER_Y, DEFAULT_PADDING } from '@/composables/diagrams/layoutConfig'
import { loadBridgeMapSpec, recalculateBridgeMapLayout } from '@/stores/specLoader/bridgeMap'
import type { DiagramNode } from '@/types'
import {
  BRIDGE_DIMENSION_LABEL_FONT_PX,
  BRIDGE_DIMENSION_LABEL_MAX_TEXT_PX,
  BRIDGE_LABEL_TO_PAIR_GAP,
  bridgeDimensionLabelText,
  measureBridgeDimensionLabel,
} from '@/utils/bridgeMapLabelLayout'
import { measureMindMapLabelWidthPx } from '@/utils/mindMapTextWrap'

const LONG_DIMENSION = '中国古典文学名著中的男性与女性代表人物对照'

function nodeByText(nodes: DiagramNode[], text: string): DiagramNode {
  const found = nodes.find((node) => node.text === text)
  if (!found?.position) throw new Error(`missing node ${text}`)
  return found
}

function layout(dimension: string) {
  const loaded = loadBridgeMapSpec({
    dimension,
    analogies: [
      { left: '孙悟空', right: '林黛玉' },
      { left: '诸葛亮', right: '貂蝉' },
    ],
  })
  return recalculateBridgeMapLayout(loaded.nodes, {})
}

describe('bridge map dimension label clearance', () => {
  it('wraps a long analogy label inside the column', () => {
    const painted = bridgeDimensionLabelText(LONG_DIMENSION)
    const unwrapped = measureMindMapLabelWidthPx(painted.value, BRIDGE_DIMENSION_LABEL_FONT_PX, {
      fontWeight: 'bold',
    })
    const longLabel = measureBridgeDimensionLabel(LONG_DIMENSION)
    const shortLabel = measureBridgeDimensionLabel('人物')

    expect(unwrapped).toBeGreaterThan(BRIDGE_DIMENSION_LABEL_MAX_TEXT_PX)
    expect(longLabel.valueMaxPx).toBeLessThanOrEqual(BRIDGE_DIMENSION_LABEL_MAX_TEXT_PX)
    expect(longLabel.valueMaxPx).toBeLessThan(unwrapped)
    expect(longLabel.width).toBeLessThan(unwrapped)
    expect(longLabel.height).toBeGreaterThan(shortLabel.height)
    expect(measureBridgeDimensionLabel('人').height).toBe(shortLabel.height)
  })

  it('starts the first pair to the right of the wrapped label', () => {
    const nodes = layout(LONG_DIMENSION)
    const label = nodes.find((node) => node.id === 'dimension-label')
    const first = nodeByText(nodes, '孙悟空')
    const box = measureBridgeDimensionLabel(LONG_DIMENSION)
    const labelX = label?.position?.x ?? 0
    const labelY = label?.position?.y ?? 0

    expect(labelX).toBe(DEFAULT_PADDING)
    expect(labelY + box.height / 2).toBeCloseTo(DEFAULT_CENTER_Y, 5)
    expect(first.position?.x ?? 0).toBeGreaterThanOrEqual(
      labelX + box.width + BRIDGE_LABEL_TO_PAIR_GAP - 0.5
    )
    expect(nodeByText(nodes, '诸葛亮').position?.x ?? 0).toBeGreaterThan(first.position?.x ?? 0)
  })

  it('moves the pairs aside when the painted label is wider than the estimate', () => {
    const loaded = loadBridgeMapSpec({
      dimension: '人物',
      analogies: [{ left: '孙悟空', right: '林黛玉' }],
    })
    const estimated = recalculateBridgeMapLayout(loaded.nodes, {})
    const wide = recalculateBridgeMapLayout(loaded.nodes, {
      'dimension-label': { width: 420, height: 96 },
    })
    const estimatedX = nodeByText(estimated, '孙悟空').position?.x ?? 0
    const wideX = nodeByText(wide, '孙悟空').position?.x ?? 0
    const wideLabel = wide.find((node) => node.id === 'dimension-label')

    expect(wideX).toBeGreaterThan(estimatedX)
    expect(wideX).toBeGreaterThanOrEqual(DEFAULT_PADDING + 420 + BRIDGE_LABEL_TO_PAIR_GAP - 0.5)
    expect((wideLabel?.position?.y ?? 0) + 96 / 2).toBeCloseTo(DEFAULT_CENTER_Y, 5)
  })
})
