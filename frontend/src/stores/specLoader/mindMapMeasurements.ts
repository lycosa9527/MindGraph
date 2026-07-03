/**
 * Mind-map node size estimation — legacy vs v2 canvas modes.
 */
import { BRANCH_NODE_HEIGHT } from '@/composables/diagrams/layoutConfig'
import {
  MIND_MAP_GEOMETRY,
  mindMapBranchFontSize,
  mindMapNodeHorizontalExtra,
  mindMapUnderlineVerticalExtra,
  MINDMAP_UNDERLINE_STROKE_WIDTH,
  computeMindMapUnderlineBoxMetrics,
} from '@/config/mindMapGeometry'
import { MIND_MAP_LEGACY_GEOMETRY } from '@/config/mindMapLegacyGeometry'
import type { MindMapCanvasMode } from '@/stores/ui'

import {
  diagramLabelLikelyNeedsRenderedMeasure,
  measureRenderedDiagramLabelHeight,
  measureTextDimensions,
  measureTextWidth,
} from './textMeasurement'
import { computeScriptAwareMaxWidth } from './textMeasurementFallback'

const BRANCH_BASE_MAX_TEXT_WIDTH = 200
const BALANCE_PADDING = 5
const TOPIC_CJK_REGEX =
  /[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]/g
const TOPIC_BASE_MAX_TEXT_WIDTH = 300

function computeBalancedMaxWidth(
  text: string,
  wrapThreshold: number,
  baseCap: number,
  fontSize: number,
  fontWeight = 'normal'
): number {
  if (typeof document === 'undefined') return wrapThreshold
  const tw = measureTextWidth(text, fontSize, { fontWeight })
  if (tw <= wrapThreshold) return wrapThreshold
  const numLines = Math.ceil(tw / baseCap)
  return Math.min(Math.ceil(tw / numLines) + BALANCE_PADDING, baseCap)
}

function resolveCanvasMode(mode?: MindMapCanvasMode): MindMapCanvasMode {
  return mode === 'legacy' ? 'legacy' : 'v2'
}

export function estimateNodeWidthForCanvasMode(
  text: string,
  nodeId?: string,
  mode?: MindMapCanvasMode
): number {
  const canvasMode = resolveCanvasMode(mode)
  if (canvasMode === 'legacy') {
    const legacy = MIND_MAP_LEGACY_GEOMETRY
    if (!text) return legacy.minNodeWidth
    if (typeof document === 'undefined') {
      return Math.max(legacy.minNodeWidth, text.length * 9 + legacy.nodeHorizontalExtra)
    }
    const fullWidth = measureTextWidth(text, legacy.branchFontSize)
    const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
    let effectiveTextWidth = fullWidth
    if (fullWidth > wrapThreshold) {
      const numLines = Math.ceil(fullWidth / BRANCH_BASE_MAX_TEXT_WIDTH)
      effectiveTextWidth = Math.ceil(fullWidth / numLines) + BALANCE_PADDING
      effectiveTextWidth = Math.min(effectiveTextWidth, BRANCH_BASE_MAX_TEXT_WIDTH)
    }
    void nodeId
    return Math.max(legacy.minNodeWidth, effectiveTextWidth + legacy.nodeHorizontalExtra)
  }

  if (!text) return MIND_MAP_GEOMETRY.minWidth
  const branchFontSize = mindMapBranchFontSize(nodeId)
  const nodeHorizontalExtra = mindMapNodeHorizontalExtra('rounded')
  const minNodeWidth = MIND_MAP_GEOMETRY.minWidth

  if (typeof document === 'undefined') {
    return Math.max(minNodeWidth, text.length * 8 + nodeHorizontalExtra)
  }

  const fullWidth = measureTextWidth(text, branchFontSize)
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
  let effectiveTextWidth = fullWidth
  if (fullWidth > wrapThreshold) {
    const numLines = Math.ceil(fullWidth / BRANCH_BASE_MAX_TEXT_WIDTH)
    effectiveTextWidth = Math.ceil(fullWidth / numLines) + BALANCE_PADDING
    effectiveTextWidth = Math.min(effectiveTextWidth, BRANCH_BASE_MAX_TEXT_WIDTH)
  }

  void nodeId
  return Math.max(minNodeWidth, effectiveTextWidth + nodeHorizontalExtra)
}

/**
 * Text block height inside an underline node — matches BranchNode display:
 * `.diagram-node-md` (line-height 1.35) + markdown pipeline when available.
 */
export function measureMindMapUnderlineTextBlockHeight(
  text: string,
  nodeId?: string
): number {
  const branchFontSize = mindMapBranchFontSize(nodeId)
  if (typeof document === 'undefined') {
    return branchFontSize * 1.35
  }
  if (!text) return branchFontSize
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
  const maxTextWidth = computeBalancedMaxWidth(
    text,
    wrapThreshold,
    BRANCH_BASE_MAX_TEXT_WIDTH,
    branchFontSize
  )
  return measureRenderedDiagramLabelHeight(text, branchFontSize, maxTextWidth)
}

/** Full underline box metrics — height and line midline offset from the same text measure. */
export function measureMindMapUnderlineBoxMetrics(
  text: string,
  nodeId?: string
): { textBlockHeight: number; totalHeight: number; lineMidlineOffsetFromTop: number } {
  const extra = mindMapUnderlineVerticalExtra()
  const branchFontSize = mindMapBranchFontSize(nodeId)
  const minTextHeight = branchFontSize
  const textBlockHeight = Math.max(
    minTextHeight,
    measureMindMapUnderlineTextBlockHeight(text, nodeId)
  )
  const { totalHeight: rawTotalHeight } = computeMindMapUnderlineBoxMetrics(textBlockHeight)
  const minHeight = branchFontSize + extra
  const totalHeight = Math.max(minHeight, Math.ceil(rawTotalHeight))
  return {
    textBlockHeight,
    totalHeight,
    lineMidlineOffsetFromTop: totalHeight - MINDMAP_UNDERLINE_STROKE_WIDTH / 2,
  }
}

export function measureBranchNodeHeightForCanvasMode(
  text: string,
  nodeId?: string,
  mode?: MindMapCanvasMode
): number {
  const canvasMode = resolveCanvasMode(mode)
  if (canvasMode === 'legacy') {
    const legacy = MIND_MAP_LEGACY_GEOMETRY
    if (!text) return BRANCH_NODE_HEIGHT
    const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
    const maxTextWidth = computeBalancedMaxWidth(
      text,
      wrapThreshold,
      BRANCH_BASE_MAX_TEXT_WIDTH,
      legacy.branchFontSize
    )
    if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
      const contentH = measureRenderedDiagramLabelHeight(text, legacy.branchFontSize, maxTextWidth)
      return Math.max(
        BRANCH_NODE_HEIGHT,
        Math.ceil(contentH + legacy.branchPaddingY + legacy.branchBorderY)
      )
    }
    const { height: textHeight } = measureTextDimensions(text, legacy.branchFontSize, {
      maxWidth: maxTextWidth,
      paddingX: 0,
      paddingY: 0,
    })
    return Math.max(
      BRANCH_NODE_HEIGHT,
      textHeight + legacy.branchPaddingY + legacy.branchBorderY
    )
  }

  if (!text) return BRANCH_NODE_HEIGHT
  const branchFontSize = mindMapBranchFontSize(nodeId)
  const branchPaddingY = MIND_MAP_GEOMETRY.paddingY * 2
  const branchBorderY = MIND_MAP_GEOMETRY.borderWidth * 2
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
  const maxTextWidth = computeBalancedMaxWidth(
    text,
    wrapThreshold,
    BRANCH_BASE_MAX_TEXT_WIDTH,
    branchFontSize
  )

  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    const contentH = measureRenderedDiagramLabelHeight(text, branchFontSize, maxTextWidth)
    return Math.max(BRANCH_NODE_HEIGHT, Math.ceil(contentH + branchPaddingY + branchBorderY))
  }

  const { height: textHeight } = measureTextDimensions(text, branchFontSize, {
    maxWidth: maxTextWidth,
    paddingX: 0,
    paddingY: 0,
  })
  return Math.max(BRANCH_NODE_HEIGHT, textHeight + branchPaddingY + branchBorderY)
}

export function measureBranchNodeUnderlineHeight(text: string, nodeId?: string): number {
  return measureMindMapUnderlineBoxMetrics(text, nodeId).totalHeight
}

export function estimateTopicNodeWidthForCanvasMode(
  text: string,
  mode?: MindMapCanvasMode
): number {
  const canvasMode = resolveCanvasMode(mode)
  if (canvasMode === 'legacy') {
    const legacy = MIND_MAP_LEGACY_GEOMETRY
    if (!text) return legacy.topicMinWidth
    if (typeof document === 'undefined') {
      const cjkMatches = text.match(TOPIC_CJK_REGEX)
      const cjkCount = cjkMatches ? cjkMatches.length : 0
      const otherCount = text.length - cjkCount
      const rawWidth = cjkCount * 19 + otherCount * 11
      return Math.max(
        legacy.topicMinWidth,
        Math.min(rawWidth, TOPIC_BASE_MAX_TEXT_WIDTH) + legacy.topicPaddingX + legacy.topicBorderX
      )
    }
    const fullWidth = measureTextWidth(text, legacy.topicFontSize, { fontWeight: 'bold' })
    let effectiveTextWidth = fullWidth
    if (fullWidth > TOPIC_BASE_MAX_TEXT_WIDTH) {
      const numLines = Math.ceil(fullWidth / TOPIC_BASE_MAX_TEXT_WIDTH)
      effectiveTextWidth = Math.ceil(fullWidth / numLines) + BALANCE_PADDING
      effectiveTextWidth = Math.min(effectiveTextWidth, TOPIC_BASE_MAX_TEXT_WIDTH)
    }
    return Math.max(
      legacy.topicMinWidth,
      effectiveTextWidth + legacy.topicPaddingX + legacy.topicBorderX
    )
  }

  if (!text) return MIND_MAP_GEOMETRY.minWidth
  const topicFontSize = MIND_MAP_GEOMETRY.topicFontSize
  const topicPaddingX = MIND_MAP_GEOMETRY.paddingX * 2
  const topicBorderX = MIND_MAP_GEOMETRY.borderWidth * 2
  const minTopicWidth = MIND_MAP_GEOMETRY.minWidth

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

  const fullWidth = measureTextWidth(text, topicFontSize, { fontWeight: 'bold' })
  let effectiveTextWidth = fullWidth
  if (fullWidth > TOPIC_BASE_MAX_TEXT_WIDTH) {
    const numLines = Math.ceil(fullWidth / TOPIC_BASE_MAX_TEXT_WIDTH)
    effectiveTextWidth = Math.ceil(fullWidth / numLines) + BALANCE_PADDING
    effectiveTextWidth = Math.min(effectiveTextWidth, TOPIC_BASE_MAX_TEXT_WIDTH)
  }

  return Math.max(minTopicWidth, effectiveTextWidth + topicPaddingX + topicBorderX)
}

export function estimateTopicNodeHeightForCanvasMode(
  text: string,
  mode?: MindMapCanvasMode
): number {
  const canvasMode = resolveCanvasMode(mode)
  if (canvasMode === 'legacy') {
    const legacy = MIND_MAP_LEGACY_GEOMETRY
    if (!text) return legacy.topicMinHeight
    const maxTextWidth = computeBalancedMaxWidth(
      text,
      TOPIC_BASE_MAX_TEXT_WIDTH,
      TOPIC_BASE_MAX_TEXT_WIDTH,
      legacy.topicFontSize,
      'bold'
    )
    const paddingY = legacy.branchPaddingY
    const borderY = legacy.branchBorderY

    if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
      const contentH = measureRenderedDiagramLabelHeight(text, legacy.topicFontSize, maxTextWidth, {
        fontWeight: 'bold',
      })
      return Math.max(legacy.topicMinHeight, Math.ceil(contentH + paddingY + borderY))
    }

    const { height: textHeight } = measureTextDimensions(text, legacy.topicFontSize, {
      fontWeight: 'bold',
      maxWidth: maxTextWidth,
      paddingX: 0,
      paddingY: 0,
    })
    const numLines = Math.max(1, Math.ceil(textHeight / legacy.topicLineHeight))
    return Math.max(legacy.topicMinHeight, numLines * legacy.topicLineHeight + paddingY + borderY)
  }

  if (!text) return MIND_MAP_GEOMETRY.minHeight
  const topicFontSize = MIND_MAP_GEOMETRY.topicFontSize
  const maxTextWidth = computeBalancedMaxWidth(
    text,
    TOPIC_BASE_MAX_TEXT_WIDTH,
    TOPIC_BASE_MAX_TEXT_WIDTH,
    topicFontSize,
    'bold'
  )
  const paddingY = MIND_MAP_GEOMETRY.paddingY * 2
  const borderY = MIND_MAP_GEOMETRY.borderWidth * 2

  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    const contentH = measureRenderedDiagramLabelHeight(text, topicFontSize, maxTextWidth, {
      fontWeight: 'bold',
    })
    return Math.max(MIND_MAP_GEOMETRY.minHeight, Math.ceil(contentH + paddingY + borderY))
  }

  const { height: textHeight } = measureTextDimensions(text, topicFontSize, {
    fontWeight: 'bold',
    maxWidth: maxTextWidth,
    paddingX: 0,
    paddingY: 0,
  })
  const lineHeight = 20
  const numLines = Math.max(1, Math.ceil(textHeight / lineHeight))
  return Math.max(MIND_MAP_GEOMETRY.minHeight, numLines * lineHeight + paddingY + borderY)
}
