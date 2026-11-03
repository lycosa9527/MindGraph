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
  bridgeDimensionValueForStorage,
  bridgeGapCenterY,
  measureBridgeDimensionLabel,
} from '@/utils/bridgeMapLabelLayout'
import {
  BRIDGE_PAIR_FONT,
  BRIDGE_PAIR_TEXT_CAP,
  bridgePairContentBox,
  bridgeSectionRight,
} from '@/utils/bridgeMapPairBox'
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

  it('clears a long second line beside the relationship', () => {
    const translate = (key: string) => (key.endsWith('analogyRelationship') ? 'As:' : '[set]')
    const gloss = 'Capital city of the country'
    const withGloss = measureBridgeDimensionLabel('都', gloss, { translate })
    const bare = measureBridgeDimensionLabel('都', undefined, { translate })

    expect(withGloss.width).toBeGreaterThan(bare.width)
    expect(withGloss.height).toBeGreaterThan(bare.height)
  })

  it('keeps the bridge in the gap when the two words have different heights', () => {
    const oldCenter = (40 + 100) / 2
    const gapCenter = bridgeGapCenterY([{ upperBottom: 80, lowerTop: 90 }])

    expect(oldCenter).toBeLessThan(80)
    expect(gapCenter).toBe(85)
  })

  it('stores the relationship without the painted brackets', () => {
    expect(bridgeDimensionValueForStorage('[首都到国家]')).toBe('首都到国家')
    expect(bridgeDimensionValueForStorage('首都到国家')).toBe('首都到国家')
  })

  it('spaces a long gloss before the browser reports a width', () => {
    const gloss = 'trigonometric functions of any angle'
    const loaded = loadBridgeMapSpec({
      dimension: '前置知识',
      analogies: [
        {
          left: '锐角三角比',
          right: '任意角',
          left_secondary: 'acute ratios',
          right_secondary: gloss,
        },
        { left: '下一对', right: '下一对右' },
      ],
    })
    const laid = recalculateBridgeMapLayout(loaded.nodes, {})
    const upper = nodeByText(laid, '锐角三角比')
    const next = nodeByText(laid, '下一对')
    const upperX = upper.position?.x
    const nextX = next.position?.x
    if (upperX == null || nextX == null) throw new Error('missing pair position')
    const section = Math.max(
      bridgePairContentBox('锐角三角比', 'acute ratios').width,
      bridgePairContentBox('任意角', gloss).width
    )

    expect(nextX - upperX).toBeCloseTo(section + 50, 4)
  })

  it('keeps a short section as wide as its text', () => {
    const laid = recalculateBridgeMapLayout(
      loadBridgeMapSpec({
        dimension: '关系',
        analogies: [
          { left: '猫', right: '铅笔' },
          { left: '狗', right: '钢笔' },
        ],
      }).nodes,
      {}
    )
    const first = nodeByText(laid, '猫')
    const next = nodeByText(laid, '狗')
    const firstX = first.position?.x
    const nextX = next.position?.x
    if (firstX == null || nextX == null) throw new Error('missing pair position')
    const section = Math.max(bridgePairContentBox('猫').width, bridgePairContentBox('铅笔').width)

    expect(section).toBeLessThan(120)
    expect(nextX - firstX).toBeCloseTo(section + 50, 4)
  })

  it('uses the wrapped line width and the extra line height', () => {
    const long = `${'unit circle definition '.repeat(20)}end`
    const wrapped = bridgePairContentBox(long)
    const bare = bridgePairContentBox('圆')
    const laid = recalculateBridgeMapLayout(
      loadBridgeMapSpec({
        dimension: '关系',
        analogies: [
          { left: long, right: '圆' },
          { left: '下一对', right: '右' },
        ],
      }).nodes,
      {}
    )
    const upper = nodeByText(laid, long)
    const next = nodeByText(laid, '下一对')
    const upperX = upper.position?.x
    const nextX = next.position?.x
    const upperY = upper.position?.y
    if (upperX == null || nextX == null || upperY == null) throw new Error('missing pair position')

    expect(wrapped.width).toBeLessThanOrEqual(BRIDGE_PAIR_TEXT_CAP)
    expect(wrapped.width).toBeLessThan(measureMindMapLabelWidthPx(long, BRIDGE_PAIR_FONT))
    expect(wrapped.height).toBeGreaterThan(bare.height)
    expect(nextX - upperX).toBeCloseTo(wrapped.width + 50, 4)
    expect(upperY).toBeLessThan(nodeByText(laid, '下一对').position?.y ?? upperY)
  })

  it('places the separator after the wider word', () => {
    expect(bridgeSectionRight(10, 240, 10, 80)).toBe(250)
    expect(bridgeSectionRight(10, 80, 10, 240)).toBe(250)
  })

  it('does not use the bridge word as the relationship gloss', () => {
    const loaded = loadBridgeMapSpec({
      dimension: '首都',
      relating_factor: 'as',
      analogies: [{ left: '北京', right: '中国' }],
      secondary: {
        relating_factor: 'as',
        analogies: [{ left: 'Beijing', right: 'China' }],
      },
    })
    const label = loaded.nodes.find((node) => node.id === 'dimension-label')

    expect(label?.text).toBe('首都')
    expect(label?.textSecondary ?? '').toBe('')
  })

  it('stamps pair and relationship glosses onto the loaded nodes', () => {
    const loaded = loadBridgeMapSpec({
      dimension: '首都',
      dimension_secondary: 'Capital of',
      analogies: [
        { left: '北京', right: '中国', left_secondary: 'Beijing', right_secondary: 'China' },
      ],
      alternative_dimensions: ['货币'],
      alternative_dimensions_secondary: ['Currency'],
    })
    const upper = nodeByText(loaded.nodes, '北京')
    const lower = nodeByText(loaded.nodes, '中国')
    const label = loaded.nodes.find((node) => node.id === 'dimension-label')

    expect(upper.textSecondary).toBe('Beijing')
    expect(lower.textSecondary).toBe('China')
    expect(label?.textSecondary).toBe('Capital of')
    expect(loaded.metadata?.alternative_dimensions_secondary).toEqual(['Currency'])
  })
})
