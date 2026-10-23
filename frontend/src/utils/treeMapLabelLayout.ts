/**
 * Tree-map classification label.
 * The painted string includes the locale prefix, and a long value wraps.
 * Categories start below that box so the label never sits on a node.
 */
import {
  DEFAULT_CENTER_X,
  NODE_MIN_DIMENSIONS,
  TREE_MAP_TOPIC_TO_CATEGORY_GAP,
} from '@/composables/diagrams/layoutConfig'
import { secondaryFontSize, stackedTextBlock } from '@/diagramBilingual/measure'
import { i18n } from '@/i18n'
import { measureTextWidth } from '@/stores/specLoader/textMeasurement'
import { measureThinkingMapLabelBlockPx } from '@/utils/mindMapTextWrap'
import { safeI18nTranslate } from '@/utils/safeI18nTranslate'

/** Wrap cap for the classification label (script-aware column scales this). */
export const TREE_MAP_DIMENSION_LABEL_MAX_TEXT_PX = 220
export const TREE_MAP_DIMENSION_LABEL_FONT_PX = 14
/** LabelNode padding: 4px 8px. */
const LABEL_PAD_X = 16
const LABEL_PAD_Y = 8
/** Gap between the topic bottom and the label. */
export const TREE_MAP_DIMENSION_GAP_ABOVE = 10
/** Gap between the label bottom and the category row. */
export const TREE_MAP_DIMENSION_GAP_BELOW = 14

type Translate = (key: string, named?: Record<string, unknown>) => string

function translate(key: string, named?: Record<string, unknown>): string {
  return safeI18nTranslate(
    (messageKey, params) => {
      if (params) return i18n.global.t(messageKey, params)
      return i18n.global.t(messageKey)
    },
    key,
    named
  )
}

/**
 * Same string LabelNode paints: `[分类维度：…]` / `[Classification by: …]`.
 * `kind` selects the tree or brace prefix. Brace maps translate the value first.
 */
export function thinkingMapDimensionLabelDisplayText(
  dimensionValue: string,
  kind: 'tree' | 'brace',
  t: Translate = translate
): string {
  const raw = dimensionValue.trim()
  const hasChinese = /[\u4e00-\u9fa5]/.test(raw)
  if (!raw) {
    const prefix =
      kind === 'brace'
        ? t('diagram.labelNode.emptyPrefixBrace')
        : t('diagram.labelNode.emptyPrefixTree')
    return t('diagram.labelNode.placeholderBracket', {
      prefix,
      hint: t('diagram.labelNode.clickToFillHint'),
    })
  }
  const prefix = hasChinese
    ? t(
        kind === 'brace'
          ? 'diagram.dimension.decompositionZh'
          : 'diagram.dimension.classificationZh'
      )
    : t(
        kind === 'brace'
          ? 'diagram.dimension.decompositionEn'
          : 'diagram.dimension.classificationEn'
      )
  return t('diagram.labelNode.placeholderBracket', { prefix, hint: raw })
}

export function measureTreeMapDimensionLabelBox(
  dimensionValue: string,
  secondary?: string
): { width: number; height: number } {
  const display = thinkingMapDimensionLabelDisplayText(dimensionValue, 'tree')
  const block = measureThinkingMapLabelBlockPx(
    display,
    TREE_MAP_DIMENSION_LABEL_FONT_PX,
    TREE_MAP_DIMENSION_LABEL_MAX_TEXT_PX,
    { fontWeight: 'normal' }
  )
  const width = Math.max(NODE_MIN_DIMENSIONS.label.minWidth, Math.ceil(block.width) + LABEL_PAD_X)
  const height = Math.max(
    NODE_MIN_DIMENSIONS.label.minHeight,
    Math.ceil(block.height) + LABEL_PAD_Y
  )
  const gloss = (secondary ?? '').trim()
  if (!gloss) return { width, height }
  const glossFont = secondaryFontSize(TREE_MAP_DIMENSION_LABEL_FONT_PX)
  const glossWidth =
    typeof document === 'undefined'
      ? Math.ceil(gloss.length * glossFont * 0.6)
      : measureTextWidth(gloss, glossFont)
  const stacked = stackedTextBlock(
    width,
    height,
    glossWidth + LABEL_PAD_X,
    TREE_MAP_DIMENSION_LABEL_FONT_PX,
    gloss
  )
  return {
    width: Math.max(NODE_MIN_DIMENSIONS.label.minWidth, stacked.width),
    height: Math.max(NODE_MIN_DIMENSIONS.label.minHeight, stacked.height),
  }
}

/**
 * DOM measurement includes the real font and locale.
 * The larger of the estimate and the DOM box is what layout clears.
 */
export function resolveTreeMapDimensionLabelBox(
  dimensionValue: string,
  secondary: string | undefined,
  pinia?: { width: number; height: number }
): { width: number; height: number } {
  const estimated = measureTreeMapDimensionLabelBox(dimensionValue, secondary)
  if (!pinia || pinia.width <= 0 || pinia.height <= 0) return estimated
  return {
    width: Math.max(estimated.width, pinia.width),
    height: Math.max(estimated.height, pinia.height),
  }
}

export function treeMapDimensionLabelPosition(
  topicTop: number,
  topicHeight: number,
  labelBox: { width: number }
): { x: number; y: number } {
  return {
    x: DEFAULT_CENTER_X - labelBox.width / 2,
    y: topicTop + topicHeight + TREE_MAP_DIMENSION_GAP_ABOVE,
  }
}

/** Category row top. With no label, the fixed topic gap is unchanged. */
export function treeMapCategoryTopY(
  topicTop: number,
  topicHeight: number,
  labelBox: { height: number } | null
): number {
  const topicBottom = topicTop + topicHeight
  if (!labelBox) return topicBottom + TREE_MAP_TOPIC_TO_CATEGORY_GAP
  return topicBottom + TREE_MAP_DIMENSION_GAP_ABOVE + labelBox.height + TREE_MAP_DIMENSION_GAP_BELOW
}
