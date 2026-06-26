/**
 * Mind-map DOM measurements when node style overrides font size/family/weight.
 * Used by learning-sheet hidden nodes and custom-styled branches.
 */
import { BRANCH_NODE_HEIGHT } from '@/composables/diagrams/layoutConfig'
import {
  MIND_MAP_GEOMETRY,
  mindMapBranchFontSize,
  mindMapNodeHorizontalExtra,
  mindMapUnderlineVerticalExtra,
} from '@/config/mindMapGeometry'
import type { NodeStyle } from '@/types'

import {
  diagramLabelLikelyNeedsRenderedMeasure,
  measureRenderedDiagramLabelHeight,
  measureTextDimensions,
  measureTextWidth,
} from './textMeasurement'
import { computeScriptAwareMaxWidth } from './textMeasurementFallback'

export type MindMapMeasureTypography = Pick<NodeStyle, 'fontSize' | 'fontWeight' | 'fontFamily'>

function resolveBranchFontSize(
  nodeId: string | undefined,
  typography?: MindMapMeasureTypography
): number {
  const custom = typography?.fontSize
  if (custom != null) {
    const n = typeof custom === 'number' ? custom : parseFloat(String(custom))
    if (Number.isFinite(n) && n > 0) return n
  }
  return mindMapBranchFontSize(nodeId)
}

function resolveTopicFontSize(typography?: MindMapMeasureTypography): number {
  const custom = typography?.fontSize
  if (custom != null) {
    const n = typeof custom === 'number' ? custom : parseFloat(String(custom))
    if (Number.isFinite(n) && n > 0) return n
  }
  return MIND_MAP_GEOMETRY.topicFontSize
}

function resolveMeasureFontWeight(
  typography: MindMapMeasureTypography | undefined,
  fallback: string
): string {
  if (typography?.fontWeight != null) return String(typography.fontWeight)
  return fallback
}

function measureOpts(typography?: MindMapMeasureTypography, fontWeight = 'normal') {
  return {
    fontWeight: resolveMeasureFontWeight(typography, fontWeight),
    fontFamily: typography?.fontFamily,
  }
}

const BRANCH_BASE_MAX_TEXT_WIDTH = 200
const BRANCH_BORDER_Y = MIND_MAP_GEOMETRY.borderWidth * 2
const BRANCH_PADDING_Y = MIND_MAP_GEOMETRY.paddingY * 2
const TOPIC_CJK_REGEX =
  /[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]/g
const TOPIC_BASE_MAX_TEXT_WIDTH = 300

function computeWrapMaxWidth(
  text: string,
  wrapThreshold: number,
  baseCap: number,
  fontSize: number,
  fontWeight = 'normal'
): number {
  if (typeof document === 'undefined') return wrapThreshold
  const tw = measureTextWidth(text, fontSize, { fontWeight })
  if (tw <= wrapThreshold) return wrapThreshold
  return baseCap
}

export function hasCustomMindMapTypography(typography?: MindMapMeasureTypography): boolean {
  return Boolean(typography?.fontSize ?? typography?.fontFamily ?? typography?.fontWeight)
}

export function estimateNodeWidthWithTypography(
  text: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): number {
  if (!text) return MIND_MAP_GEOMETRY.minWidth
  const branchFontSize = resolveBranchFontSize(nodeId, typography)
  const nodeHorizontalExtra = mindMapNodeHorizontalExtra('rounded')
  const minNodeWidth = MIND_MAP_GEOMETRY.minWidth
  const weight = resolveMeasureFontWeight(typography, 'normal')

  if (typeof document === 'undefined') {
    return Math.max(minNodeWidth, text.length * 8 + nodeHorizontalExtra)
  }

  const fullWidth = measureTextWidth(text, branchFontSize, measureOpts(typography, weight))
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
  const effectiveTextWidth =
    fullWidth > wrapThreshold ? BRANCH_BASE_MAX_TEXT_WIDTH : fullWidth

  void nodeId
  return Math.max(minNodeWidth, effectiveTextWidth + nodeHorizontalExtra)
}

export function measureBranchNodeHeightWithTypography(
  text: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): number {
  if (!text) return BRANCH_NODE_HEIGHT
  const branchFontSize = resolveBranchFontSize(nodeId, typography)
  const fontWeight = resolveMeasureFontWeight(typography, 'normal')
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
  const maxTextWidth = computeWrapMaxWidth(
    text,
    wrapThreshold,
    BRANCH_BASE_MAX_TEXT_WIDTH,
    branchFontSize,
    fontWeight
  )

  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    const contentH = measureRenderedDiagramLabelHeight(text, branchFontSize, maxTextWidth, {
      fontWeight,
      fontFamily: typography?.fontFamily,
    })
    return Math.max(BRANCH_NODE_HEIGHT, Math.ceil(contentH + BRANCH_PADDING_Y + BRANCH_BORDER_Y))
  }

  const { height: textHeight } = measureTextDimensions(text, branchFontSize, {
    maxWidth: maxTextWidth,
    paddingX: 0,
    paddingY: 0,
    fontWeight,
    fontFamily: typography?.fontFamily,
  })
  return Math.max(BRANCH_NODE_HEIGHT, textHeight + BRANCH_PADDING_Y + BRANCH_BORDER_Y)
}

export function measureBranchNodeUnderlineHeightWithTypography(
  text: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): number {
  const extra = mindMapUnderlineVerticalExtra()
  const branchFontSize = resolveBranchFontSize(nodeId, typography)
  const fontWeight = resolveMeasureFontWeight(typography, 'normal')
  const minHeight = branchFontSize + extra
  if (!text) return minHeight
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
  const maxTextWidth = computeWrapMaxWidth(
    text,
    wrapThreshold,
    BRANCH_BASE_MAX_TEXT_WIDTH,
    branchFontSize,
    fontWeight
  )

  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    const contentH = measureRenderedDiagramLabelHeight(text, branchFontSize, maxTextWidth, {
      fontWeight,
      fontFamily: typography?.fontFamily,
    })
    return Math.max(minHeight, Math.ceil(contentH + extra))
  }

  const { height: textHeight } = measureTextDimensions(text, branchFontSize, {
    maxWidth: maxTextWidth,
    paddingX: 0,
    paddingY: 0,
    fontWeight,
    fontFamily: typography?.fontFamily,
  })
  return Math.max(minHeight, textHeight + extra)
}

export function estimateTopicNodeWidthWithTypography(
  text: string,
  typography?: MindMapMeasureTypography
): number {
  if (!text) return MIND_MAP_GEOMETRY.minWidth
  const topicFontSize = resolveTopicFontSize(typography)
  const topicPaddingX = MIND_MAP_GEOMETRY.paddingX * 2
  const topicBorderX = MIND_MAP_GEOMETRY.borderWidth * 2
  const minTopicWidth = MIND_MAP_GEOMETRY.minWidth
  const fontWeight = resolveMeasureFontWeight(typography, 'bold')

  if (typeof document === 'undefined') {
    const cjkMatches = text.match(TOPIC_CJK_REGEX)
    const cjkCount = cjkMatches ? cjkMatches.length : 0
    const otherCount = text.length - cjkCount
    const rawWidth = cjkCount * 19 + otherCount * 11
    return Math.max(
      minTopicWidth,
      Math.min(rawWidth, TOPIC_BASE_MAX_TEXT_WIDTH) + topicPaddingX + topicBorderX
    )
  }

  const fullWidth = measureTextWidth(text, topicFontSize, measureOpts(typography, fontWeight))
  const effectiveTextWidth =
    fullWidth > TOPIC_BASE_MAX_TEXT_WIDTH ? TOPIC_BASE_MAX_TEXT_WIDTH : fullWidth

  return Math.max(minTopicWidth, effectiveTextWidth + topicPaddingX + topicBorderX)
}

export function estimateTopicNodeHeightWithTypography(
  text: string,
  typography?: MindMapMeasureTypography
): number {
  if (!text) return MIND_MAP_GEOMETRY.minHeight
  const topicFontSize = resolveTopicFontSize(typography)
  const fontWeight = resolveMeasureFontWeight(typography, 'bold')
  const maxTextWidth = computeWrapMaxWidth(
    text,
    TOPIC_BASE_MAX_TEXT_WIDTH,
    TOPIC_BASE_MAX_TEXT_WIDTH,
    topicFontSize,
    fontWeight
  )
  const paddingY = MIND_MAP_GEOMETRY.paddingY * 2
  const borderY = MIND_MAP_GEOMETRY.borderWidth * 2

  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    const contentH = measureRenderedDiagramLabelHeight(text, topicFontSize, maxTextWidth, {
      fontWeight,
      fontFamily: typography?.fontFamily,
    })
    return Math.max(MIND_MAP_GEOMETRY.minHeight, Math.ceil(contentH + paddingY + borderY))
  }

  const { height: textHeight } = measureTextDimensions(text, topicFontSize, {
    fontWeight,
    fontFamily: typography?.fontFamily,
    maxWidth: maxTextWidth,
    paddingX: 0,
    paddingY: 0,
  })
  const lineHeight = Math.ceil(topicFontSize * 1.25)
  const numLines = Math.max(1, Math.ceil(textHeight / lineHeight))
  return Math.max(MIND_MAP_GEOMETRY.minHeight, numLines * lineHeight + paddingY + borderY)
}
