/**
 * Mind-map node size estimation — legacy vs v2 canvas modes.
 */
import { BRANCH_NODE_HEIGHT } from '@/composables/diagrams/layoutConfig'
import {
  MINDMAP_UNDERLINE_STROKE_WIDTH,
  MIND_MAP_GEOMETRY,
  computeMindMapUnderlineBoxMetrics,
  mindMapBranchFontSize,
  mindMapNodeHorizontalExtra,
  mindMapUnderlineVerticalExtra,
} from '@/config/mindMapGeometry'
import { MIND_MAP_LEGACY_GEOMETRY } from '@/config/mindMapLegacyGeometry'
import { BILINGUAL_SECONDARY_LINE_HEIGHT, secondaryFontSize } from '@/diagramBilingual/measure'
import { diagramPaintFontFamily } from '@/fonts/diagramCanvasFonts'
import type { MindMapCanvasMode } from '@/stores/ui'
import {
  MIND_MAP_BRANCH_MAX_TEXT_WIDTH,
  MIND_MAP_TEXT_LINE_HEIGHT,
  MIND_MAP_UNDERLINE_TEXT_LINE_HEIGHT,
  estimateMindMapNumberedContentWidthPx,
  measureMindMapBranchPaintedBlockPx,
  measureMindMapLabelWidthPx,
  measureMindMapNumberPrefixAdvancePx,
  resolveMindMapBranchBodyMaxWidthPx,
} from '@/utils/mindMapTextWrap'
import type { NodeShape } from '@/utils/nodeShapeStyle'

import {
  diagramLabelLikelyNeedsRenderedMeasure,
  measureCssWrappedBlockPx,
  measureRenderedDiagramLabelHeight,
  measureTextDimensions,
  measureTextWidth,
} from './textMeasurement'
import { computeScriptAwareMaxWidth } from './textMeasurementFallback'

export type MindMapNumberedFont = {
  fontSize?: number
  fontWeight?: string
  fontFamily?: string
}

function resolveNumberedFontSize(nodeId: string | undefined, font?: MindMapNumberedFont): number {
  const custom = font?.fontSize
  if (custom != null && Number.isFinite(custom) && custom > 0) return custom
  return mindMapBranchFontSize(nodeId)
}

/** Layout estimate shape — oval uses wider horizontal padding than rounded/rectangle. */
export function resolveMindMapMeasureShape(shape?: NodeShape | null): NodeShape {
  return shape ?? 'rounded'
}

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
  mode?: MindMapCanvasMode,
  shape?: NodeShape | null
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
  const nodeHorizontalExtra = mindMapNodeHorizontalExtra(resolveMindMapMeasureShape(shape))
  const minNodeWidth = MIND_MAP_GEOMETRY.minWidth

  const block = measureMindMapBranchPaintedBlockPx(text, branchFontSize)
  void nodeId
  return Math.max(minNodeWidth, block.width + nodeHorizontalExtra)
}

/**
 * Text block height inside an underline node — matches BranchNode display:
 * `.diagram-node-md` (line-height 1.35) + markdown pipeline when available.
 */
export function measureMindMapUnderlineTextBlockHeight(text: string, nodeId?: string): number {
  const branchFontSize = mindMapBranchFontSize(nodeId)
  if (typeof document === 'undefined') {
    return branchFontSize * 1.35
  }
  if (!text) return branchFontSize
  const block = measureMindMapBranchPaintedBlockPx(text, branchFontSize)
  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    return measureRenderedDiagramLabelHeight(text, branchFontSize, Math.max(block.width, 1))
  }
  return Math.max(
    branchFontSize,
    block.lineCount * branchFontSize * MIND_MAP_UNDERLINE_TEXT_LINE_HEIGHT
  )
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
    return Math.max(BRANCH_NODE_HEIGHT, textHeight + legacy.branchPaddingY + legacy.branchBorderY)
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
  mode?: MindMapCanvasMode,
  shape?: NodeShape | null
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
  const topicHorizontalExtra = mindMapNodeHorizontalExtra(resolveMindMapMeasureShape(shape))
  const minTopicWidth = MIND_MAP_GEOMETRY.minWidth

  if (typeof document === 'undefined') {
    const cjkMatches = text.match(TOPIC_CJK_REGEX)
    const cjkCount = cjkMatches ? cjkMatches.length : 0
    const otherCount = text.length - cjkCount
    const rawWidth = cjkCount * 19 + otherCount * 11
    return Math.max(
      minTopicWidth,
      Math.min(rawWidth, TOPIC_BASE_MAX_TEXT_WIDTH) + topicHorizontalExtra
    )
  }

  const painted = measurePaintedTopicBlock(text, topicFontSize, 'bold')
  if (painted) return Math.max(minTopicWidth, painted.width + topicHorizontalExtra)

  const fullWidth = measureTextWidth(text, topicFontSize, { fontWeight: 'bold' })
  let effectiveTextWidth = fullWidth
  if (fullWidth > TOPIC_BASE_MAX_TEXT_WIDTH) {
    const numLines = Math.ceil(fullWidth / TOPIC_BASE_MAX_TEXT_WIDTH)
    effectiveTextWidth = Math.ceil(fullWidth / numLines) + BALANCE_PADDING
    effectiveTextWidth = Math.min(effectiveTextWidth, TOPIC_BASE_MAX_TEXT_WIDTH)
  }

  return Math.max(minTopicWidth, effectiveTextWidth + topicHorizontalExtra)
}

/**
 * Topic text block as the topic node paints it: a 300px column with
 * balanced lines. Balance shortens the lines, not the box, so a wrapped
 * topic is the full column wide. Null outside a real browser.
 */
export function measurePaintedTopicBlock(
  text: string,
  fontSize: number,
  fontWeight: string,
  fontFamily?: string
): { width: number; height: number } | null {
  const painted = measureCssWrappedBlockPx(text, fontSize, TOPIC_BASE_MAX_TEXT_WIDTH, {
    fontWeight,
    fontFamily: diagramPaintFontFamily(fontFamily, MIND_MAP_GEOMETRY.fontFamily),
  })
  if (!painted) return null
  const lineHeightPx = fontSize * MIND_MAP_TEXT_LINE_HEIGHT
  const lines = Math.max(1, Math.round(painted.height / lineHeightPx) || 1)
  return { width: painted.width, height: lines * lineHeightPx }
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
  const paddingY = MIND_MAP_GEOMETRY.paddingY * 2
  const borderY = MIND_MAP_GEOMETRY.borderWidth * 2
  const painted = diagramLabelLikelyNeedsRenderedMeasure(text)
    ? null
    : measurePaintedTopicBlock(text, topicFontSize, 'bold')
  if (painted) {
    return Math.max(MIND_MAP_GEOMETRY.minHeight, Math.round(painted.height + paddingY + borderY))
  }
  const maxTextWidth = computeBalancedMaxWidth(
    text,
    TOPIC_BASE_MAX_TEXT_WIDTH,
    TOPIC_BASE_MAX_TEXT_WIDTH,
    topicFontSize,
    'bold'
  )

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

/** Box width for prefix chrome + body. Empty prefix uses the un-numbered v2 estimate. */
export function estimateNumberedBranchBoxWidth(
  label: string,
  prefix: string,
  nodeId?: string,
  shape?: NodeShape | null,
  font?: MindMapNumberedFont
): number {
  if (!prefix) {
    return estimateNodeWidthForCanvasMode(label, nodeId, 'v2', shape)
  }
  const fontSize = resolveNumberedFontSize(nodeId, font)
  const content = estimateMindMapNumberedContentWidthPx(label, prefix, fontSize, {
    fontWeight: font?.fontWeight ?? 'normal',
    fontFamily: font?.fontFamily,
  })
  const textCol = Math.min(content, MIND_MAP_BRANCH_MAX_TEXT_WIDTH)
  return Math.max(
    MIND_MAP_GEOMETRY.minWidth,
    textCol + mindMapNodeHorizontalExtra(resolveMindMapMeasureShape(shape))
  )
}

function numberedBodyWrapWidth(
  label: string,
  prefix: string,
  nodeId: string | undefined,
  font?: MindMapNumberedFont
): { fontSize: number; maxTextWidth: number; fontWeight: string; fontFamily: string | undefined } {
  const fontSize = resolveNumberedFontSize(nodeId, font)
  const fontWeight = font?.fontWeight ?? 'normal'
  const fontFamily = font?.fontFamily
  const maxTextWidth = resolveMindMapBranchBodyMaxWidthPx(label, prefix, fontSize, {
    fontWeight,
    fontFamily,
  })
  return { fontSize, maxTextWidth, fontWeight, fontFamily }
}

/** Height of the body wrap column beside prefix chrome (v2). */
export function measureNumberedBranchHeightForCanvasMode(
  label: string,
  prefix: string,
  nodeId?: string,
  mode?: MindMapCanvasMode,
  font?: MindMapNumberedFont
): number {
  if (!prefix) {
    return measureBranchNodeHeightForCanvasMode(label, nodeId, mode)
  }
  const text = (label || '').trim()
  if (!text) return BRANCH_NODE_HEIGHT
  const { fontSize, maxTextWidth, fontWeight, fontFamily } = numberedBodyWrapWidth(
    text,
    prefix,
    nodeId,
    font
  )
  const branchPaddingY = MIND_MAP_GEOMETRY.paddingY * 2
  const branchBorderY = MIND_MAP_GEOMETRY.borderWidth * 2
  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    const contentH = measureRenderedDiagramLabelHeight(text, fontSize, maxTextWidth, {
      fontWeight,
      fontFamily,
    })
    return Math.max(BRANCH_NODE_HEIGHT, Math.ceil(contentH + branchPaddingY + branchBorderY))
  }
  const { height: textHeight } = measureTextDimensions(text, fontSize, {
    maxWidth: maxTextWidth,
    paddingX: 0,
    paddingY: 0,
    fontWeight,
    fontFamily,
  })
  return Math.max(BRANCH_NODE_HEIGHT, textHeight + branchPaddingY + branchBorderY)
}

/**
 * Grow a branch box for the bilingual second line. The gloss paints inside the
 * label's wrap column at 0.75em / line-height 1.2, beside any number prefix, so
 * a short CJK label can carry a much wider English line and a wrapped label
 * wraps its gloss onto several lines.
 */
export function withMindMapBranchSecondaryBox(
  box: { width: number; height: number },
  label: string,
  prefix: string,
  secondary: string | undefined,
  options: { nodeId?: string; shape?: NodeShape | null; font?: MindMapNumberedFont }
): { width: number; height: number } {
  const gloss = (secondary ?? '').trim()
  if (!gloss) return box
  const fontSize = resolveNumberedFontSize(options.nodeId, options.font)
  const fontFamily = diagramPaintFontFamily(options.font?.fontFamily, MIND_MAP_GEOMETRY.fontFamily)
  const primaryOptions = { fontWeight: options.font?.fontWeight ?? 'normal', fontFamily }
  const column = resolveMindMapBranchBodyMaxWidthPx(
    (label || '').trim(),
    prefix,
    fontSize,
    primaryOptions
  )
  const glossFontSize = secondaryFontSize(fontSize)
  const glossOptions = { fontWeight: 'normal', fontFamily }
  const single = measureMindMapLabelWidthPx(gloss, glossFontSize, glossOptions)
  let lineCount = 1
  if (single > column) {
    const painted = measureCssWrappedBlockPx(gloss, glossFontSize, column, glossOptions)
    lineCount = painted
      ? Math.max(1, Math.round(painted.height / (glossFontSize * MIND_MAP_TEXT_LINE_HEIGHT)))
      : Math.ceil(single / column)
  }
  const contentWidth =
    Math.min(single, column) + measureMindMapNumberPrefixAdvancePx(prefix, fontSize, primaryOptions)
  const horizontalExtra = mindMapNodeHorizontalExtra(resolveMindMapMeasureShape(options.shape))
  return {
    width: Math.max(box.width, Math.ceil(contentWidth + horizontalExtra)),
    height: box.height + Math.ceil(lineCount * glossFontSize * BILINGUAL_SECONDARY_LINE_HEIGHT),
  }
}

/** Underline box metrics using the body wrap column beside prefix chrome. */
export function measureNumberedUnderlineBoxMetrics(
  label: string,
  prefix: string,
  nodeId?: string,
  font?: MindMapNumberedFont
): { textBlockHeight: number; totalHeight: number; lineMidlineOffsetFromTop: number } {
  if (!prefix) {
    return measureMindMapUnderlineBoxMetrics(label, nodeId)
  }
  const extra = mindMapUnderlineVerticalExtra()
  const { fontSize, maxTextWidth, fontWeight, fontFamily } = numberedBodyWrapWidth(
    (label || '').trim(),
    prefix,
    nodeId,
    font
  )
  const minTextHeight = fontSize
  const text = (label || '').trim()
  let textBlockHeight = minTextHeight
  if (text) {
    if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
      textBlockHeight = Math.max(
        minTextHeight,
        measureRenderedDiagramLabelHeight(text, fontSize, maxTextWidth, {
          fontWeight,
          fontFamily,
        })
      )
    } else {
      const { height: textHeight } = measureTextDimensions(text, fontSize, {
        maxWidth: maxTextWidth,
        paddingX: 0,
        paddingY: 0,
        fontWeight,
        fontFamily,
      })
      textBlockHeight = Math.max(minTextHeight, textHeight * (1.35 / 1.4))
    }
  }
  const { totalHeight: rawTotalHeight } = computeMindMapUnderlineBoxMetrics(textBlockHeight)
  const minHeight = fontSize + extra
  const totalHeight = Math.max(minHeight, Math.ceil(rawTotalHeight))
  return {
    textBlockHeight,
    totalHeight,
    lineMidlineOffsetFromTop: totalHeight - MINDMAP_UNDERLINE_STROKE_WIDTH / 2,
  }
}
