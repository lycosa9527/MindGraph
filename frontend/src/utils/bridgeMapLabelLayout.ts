/**
 * Bridge-map dimension label.
 * The painted label is two blocks: the analogy prefix, then the bracketed value.
 * A value that fits the script-aware column stays one line. A longer value wraps
 * at the map's own cap, and the first pair starts to the right of that box.
 */
import { DEFAULT_PADDING, NODE_MIN_DIMENSIONS } from '@/composables/diagrams/layoutConfig'
import { secondaryFontSize } from '@/diagramBilingual/measure'
import { i18n } from '@/i18n'
import type { DiagramNode } from '@/types'
import { BRIDGE_DIMENSION_LABEL_ID } from '@/utils/bridgeMapIdentity'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import {
  measureThinkingMapLabelBlockPx,
  resolveThinkingMapDisplayMaxWidthPx,
} from '@/utils/mindMapTextWrap'
import { safeI18nTranslate } from '@/utils/safeI18nTranslate'

/** Wrap cap for the analogy label (script-aware column scales this). */
export const BRIDGE_DIMENSION_LABEL_MAX_TEXT_PX = 180
export const BRIDGE_DIMENSION_LABEL_FONT_PX = 14
/** Gap from the label's right edge to the first pair (bridge line start). */
export const BRIDGE_LABEL_TO_PAIR_GAP = 10

/** LabelNode padding: 4px 8px. */
const LABEL_PAD_X = 16
const LABEL_PAD_Y = 8
/** Margin between the prefix line and the value line. */
const LABEL_LINE_GAP = 2

type Translate = (key: string) => string

export type BridgeLabelMeasureOptions = {
  fontSize?: number
  fontFamily?: string
  fontWeight?: string
  translate?: Translate
}

export type BridgeDimensionLabelText = {
  prefix: string
  value: string
  isPlaceholder: boolean
}

export type BridgeDimensionLabelMetrics = {
  prefixMaxPx: number
  valueMaxPx: number
  boxMaxPx: number
  width: number
  height: number
}

function translate(key: string): string {
  return safeI18nTranslate((messageKey) => i18n.global.t(messageKey), key)
}

function paintedValue(raw: string, t: Translate): { value: string; isPlaceholder: boolean } {
  let text = raw.trim()
  if (text.startsWith('[') && text.endsWith(']')) {
    text = text.slice(1, -1).trim()
  }
  if (!text) {
    return { value: t('diagram.labelNode.clickToSet'), isPlaceholder: true }
  }
  return { value: `[${text}]`, isPlaceholder: false }
}

/** Same strings LabelNode paints: prefix, then `[dimension]` or the empty hint. */
export function bridgeDimensionLabelText(
  dimensionValue: string,
  t: Translate = translate
): BridgeDimensionLabelText {
  const painted = paintedValue(dimensionValue, t)
  return {
    prefix: t('diagram.labelNode.analogyRelationship'),
    value: painted.value,
    isPlaceholder: painted.isPlaceholder,
  }
}

function measureOptions(options: BridgeLabelMeasureOptions | undefined): {
  fontSize: number
  fontFamily: string
  fontWeight: string
  t: Translate
} {
  const fontSize =
    options?.fontSize && options.fontSize > 0 ? options.fontSize : BRIDGE_DIMENSION_LABEL_FONT_PX
  return {
    fontSize,
    fontFamily: options?.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontWeight: options?.fontWeight || 'bold',
    t: options?.translate ?? translate,
  }
}

/**
 * Content box for the painted label.
 * Width is the wider of the two blocks after wrapping, plus padding.
 * Height stacks the prefix, the gap, the wrapped value, and an optional gloss.
 */
export function measureBridgeDimensionLabel(
  dimensionValue: string,
  secondary?: string,
  options?: BridgeLabelMeasureOptions
): BridgeDimensionLabelMetrics {
  const { fontSize, fontFamily, fontWeight, t } = measureOptions(options)
  const paint = bridgeDimensionLabelText(dimensionValue, t)
  const font = { fontWeight, fontFamily }
  const prefixBlock = measureThinkingMapLabelBlockPx(
    paint.prefix,
    fontSize,
    BRIDGE_DIMENSION_LABEL_MAX_TEXT_PX,
    font
  )
  const valueBlock = measureThinkingMapLabelBlockPx(
    paint.value,
    fontSize,
    BRIDGE_DIMENSION_LABEL_MAX_TEXT_PX,
    font
  )
  const prefixMaxPx = resolveThinkingMapDisplayMaxWidthPx(
    paint.prefix,
    fontSize,
    BRIDGE_DIMENSION_LABEL_MAX_TEXT_PX,
    font
  )
  const valueMaxPx = resolveThinkingMapDisplayMaxWidthPx(
    paint.value,
    fontSize,
    BRIDGE_DIMENSION_LABEL_MAX_TEXT_PX,
    font
  )
  const column = Math.max(prefixMaxPx, valueMaxPx)
  let textHeight = prefixBlock.height + LABEL_LINE_GAP + valueBlock.height
  const gloss = (secondary ?? '').trim()
  if (gloss) {
    const glossBlock = measureThinkingMapLabelBlockPx(
      gloss,
      secondaryFontSize(fontSize),
      BRIDGE_DIMENSION_LABEL_MAX_TEXT_PX,
      { fontWeight: 'normal', fontFamily }
    )
    textHeight += glossBlock.height
  }
  const textWidth = Math.max(prefixBlock.width, valueBlock.width)
  const width = Math.max(
    NODE_MIN_DIMENSIONS.label.minWidth,
    Math.min(Math.ceil(textWidth), Math.ceil(column)) + LABEL_PAD_X
  )
  const height = Math.max(NODE_MIN_DIMENSIONS.label.minHeight, Math.ceil(textHeight) + LABEL_PAD_Y)
  return {
    prefixMaxPx,
    valueMaxPx,
    boxMaxPx: Math.max(width, Math.ceil(column) + LABEL_PAD_X),
    width,
    height,
  }
}

export function measureBridgeDimensionLabelBox(
  dimensionValue: string,
  secondary?: string,
  options?: BridgeLabelMeasureOptions
): { width: number; height: number } {
  const metrics = measureBridgeDimensionLabel(dimensionValue, secondary, options)
  return { width: metrics.width, height: metrics.height }
}

/**
 * DOM measurement includes the real font and locale.
 * The larger of the estimate and the DOM box is what layout clears.
 */
export function resolveBridgeDimensionLabelBox(
  node: DiagramNode,
  pinia?: { width: number; height: number }
): { width: number; height: number } {
  const fontSize = node.style?.fontSize
  const estimated = measureBridgeDimensionLabelBox(node.text ?? '', node.textSecondary, {
    fontSize,
    fontFamily: node.style?.fontFamily,
    fontWeight: node.style?.fontWeight || 'bold',
  })
  if (!pinia || pinia.width <= 0 || pinia.height <= 0) return estimated
  return {
    width: Math.max(estimated.width, pinia.width),
    height: Math.max(estimated.height, pinia.height),
  }
}

export type BridgePairOrigin = {
  pairStartX: number
  label: { x: number; y: number } | null
}

/** First pair's left edge, and where the dimension label sits on the bridge. */
export function resolveBridgePairOrigin(
  nodes: DiagramNode[],
  nodeDimensions: Record<string, { width: number; height: number }>,
  centerY: number
): BridgePairOrigin {
  const label = nodes.find((node) => node.id === BRIDGE_DIMENSION_LABEL_ID)
  if (!label) {
    const leftmost = nodes.reduce<number | null>((min, node) => {
      if (node.id === BRIDGE_DIMENSION_LABEL_ID || node.position?.x == null) return min
      return min == null || node.position.x < min ? node.position.x : min
    }, null)
    const fallback = DEFAULT_PADDING + NODE_MIN_DIMENSIONS.label.minWidth + BRIDGE_LABEL_TO_PAIR_GAP
    return {
      pairStartX: leftmost ?? fallback,
      label: null,
    }
  }
  const box = resolveBridgeDimensionLabelBox(label, nodeDimensions[label.id])
  const labelX = DEFAULT_PADDING
  return {
    pairStartX: labelX + box.width + BRIDGE_LABEL_TO_PAIR_GAP,
    label: { x: labelX, y: centerY - box.height / 2 },
  }
}
