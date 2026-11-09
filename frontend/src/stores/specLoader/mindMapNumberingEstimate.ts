/**
 * Branch sizes for a numbering toggle.
 * Two layout reads for the whole map (nowrap widths, then wrapped heights).
 * The existing per-node estimators run once and read those results.
 */
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { diagramPaintFontFamily } from '@/fonts/diagramCanvasFonts'
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import {
  type MindMapBranchPaintBox,
  createMindMapBranchPaintIndex,
} from '@/utils/mindMapBranchPaintBox'
import { resolveMindMapBranchBodyMaxWidthPx } from '@/utils/mindMapTextWrap'
import { resolveNodeShape } from '@/utils/nodeShapeStyle'

import {
  estimateNumberedBranchWidth,
  measureNumberedBranchHeight,
  measureNumberedBranchUnderlineHeight,
} from './mindMap'
import { learningSheetLayoutText } from './mindMapLearningSheet'
import { hasCustomMindMapTypography } from './mindMapTypographyMeasure'
import {
  type BoxMeasureSpec,
  type NowrapMeasureSpec,
  measureBoxBatch,
  measureNowrapBatch,
  plainTextBoxKey,
  plainTextNowrapKey,
  withPlainTextMeasureLookup,
} from './plainTextMeasureBatch'
import { diagramLabelLikelyNeedsRenderedMeasure, measureTextWidth } from './textMeasurement'
import { computeScriptAwareMaxWidth } from './textMeasurementFallback'

const BRANCH_TEXT_MAX = 200
const BALANCE_PADDING = 5

export type MindMapBranchSize = {
  width: number
  height: number
}

type MeasureFont = {
  fontSize: number
  fontWeight: string
  fontFamily: string | undefined
}

/** `measureMindMapLabelWidthPx` collapses weight to bold or normal before measuring. */
function labelMeasureWeight(weight: string): string {
  return weight === 'bold' || weight === '700' ? 'bold' : 'normal'
}

function isTopic(node: DiagramNode): boolean {
  return node.id === 'topic' || node.type === 'topic' || node.type === 'center'
}

type PaintOf = (node: DiagramNode) => MindMapBranchPaintBox

function measureFont(node: DiagramNode, paintOf: PaintOf): MeasureFont {
  const box = paintOf(node)
  const fontFamily = diagramPaintFontFamily(node.style?.fontFamily, MIND_MAP_GEOMETRY.fontFamily)
  return {
    fontSize: box.fontSize,
    fontWeight: node.style?.fontWeight != null ? String(node.style.fontWeight) : 'normal',
    fontFamily,
  }
}

function paintedStyle(node: DiagramNode, box: MindMapBranchPaintBox): NodeStyle {
  return {
    ...node.style,
    fontSize: box.fontSize,
    fontFamily: diagramPaintFontFamily(node.style?.fontFamily, MIND_MAP_GEOMETRY.fontFamily),
  }
}

function rememberNowrap(
  specs: NowrapMeasureSpec[],
  seen: Set<string>,
  text: string,
  font: MeasureFont,
  fontFamily: string
): void {
  const label = (text || '').trim()
  if (!label) return
  const key = plainTextNowrapKey(label, font.fontSize, font.fontWeight, fontFamily)
  if (seen.has(key)) return
  seen.add(key)
  specs.push({
    key,
    text: label,
    fontSize: font.fontSize,
    fontWeight: font.fontWeight,
    fontFamily,
  })
}

function nowrapSpecs(
  nodes: DiagramNode[],
  numberMap: Map<string, string>,
  paintOf: PaintOf
): NowrapMeasureSpec[] {
  const specs: NowrapMeasureSpec[] = []
  const seen = new Set<string>()
  for (const node of nodes) {
    if (isTopic(node)) continue
    const text = learningSheetLayoutText(node)
    const prefix = numberMap.get(node.id) ?? ''
    const font = measureFont(node, paintOf)
    if (prefix) {
      const family = font.fontFamily ?? MIND_MAP_GEOMETRY.fontFamily
      const measured = { ...font, fontWeight: labelMeasureWeight(font.fontWeight) }
      rememberNowrap(specs, seen, text, measured, family)
      rememberNowrap(specs, seen, prefix, measured, family)
      rememberNowrap(specs, seen, `${prefix} ${text}`.trim(), measured, family)
      continue
    }
    rememberNowrap(specs, seen, text, font, font.fontFamily ?? DIAGRAM_NODE_FONT_STACK)
  }
  return specs
}

/** Same wrap column as the v2 branch height estimators, using cached nowrap widths. */
function wrapMaxWidth(text: string, prefix: string, node: DiagramNode, font: MeasureFont): number {
  if (prefix) {
    return resolveMindMapBranchBodyMaxWidthPx(text, prefix, font.fontSize, {
      fontWeight: font.fontWeight,
      fontFamily: font.fontFamily,
    })
  }
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_TEXT_MAX)
  if (typeof document === 'undefined') return wrapThreshold
  const measured = measureTextWidth(text, font.fontSize, {
    fontWeight: font.fontWeight,
    fontFamily: font.fontFamily,
  })
  if (hasCustomMindMapTypography(node.style)) {
    return measured > wrapThreshold ? BRANCH_TEXT_MAX : wrapThreshold
  }
  if (measured <= wrapThreshold) return wrapThreshold
  const lineCount = Math.ceil(measured / BRANCH_TEXT_MAX)
  return Math.min(Math.ceil(measured / lineCount) + BALANCE_PADDING, BRANCH_TEXT_MAX)
}

function boxSpecs(
  nodes: DiagramNode[],
  numberMap: Map<string, string>,
  paintOf: PaintOf
): BoxMeasureSpec[] {
  const specs: BoxMeasureSpec[] = []
  const seen = new Set<string>()
  for (const node of nodes) {
    if (isTopic(node)) continue
    const text = (learningSheetLayoutText(node) || '').trim()
    if (!text || diagramLabelLikelyNeedsRenderedMeasure(text)) continue
    const prefix = numberMap.get(node.id) ?? ''
    const underlineCustom =
      !prefix &&
      resolveNodeShape(node.style, true) === 'underline' &&
      hasCustomMindMapTypography(node.style)
    if (underlineCustom) continue
    const font = measureFont(node, paintOf)
    const maxWidth = wrapMaxWidth(text, prefix, node, font)
    const fontFamily = font.fontFamily ?? DIAGRAM_NODE_FONT_STACK
    const key = plainTextBoxKey(text, font.fontSize, font.fontWeight, fontFamily, maxWidth, 0, 0)
    if (seen.has(key)) continue
    seen.add(key)
    specs.push({
      key,
      text,
      fontSize: font.fontSize,
      fontWeight: font.fontWeight,
      fontFamily,
      maxWidth,
      paddingX: 0,
      paddingY: 0,
    })
  }
  return specs
}

function branchHeight(
  node: DiagramNode,
  text: string,
  prefix: string,
  box: MindMapBranchPaintBox
): number {
  const style = paintedStyle(node, box)
  if (box.shape === 'underline') {
    return measureNumberedBranchUnderlineHeight(text, prefix, node.id, style)
  }
  return measureNumberedBranchHeight(text, prefix, node.id, style)
}

export function estimateMindMapBranchSizes(
  nodes: DiagramNode[],
  numberMap: Map<string, string>,
  connections?: Connection[] | null,
  diagramStyleId?: string | null
): Map<string, MindMapBranchSize> {
  const paintOf = createMindMapBranchPaintIndex(connections, diagramStyleId)
  const widths = measureNowrapBatch(nowrapSpecs(nodes, numberMap, paintOf))
  const boxes = withPlainTextMeasureLookup(widths, new Map(), () =>
    measureBoxBatch(boxSpecs(nodes, numberMap, paintOf))
  )
  const sizes = new Map<string, MindMapBranchSize>()
  withPlainTextMeasureLookup(widths, boxes, () => {
    for (const node of nodes) {
      if (isTopic(node)) continue
      const text = learningSheetLayoutText(node)
      const prefix = numberMap.get(node.id) ?? ''
      const box = paintOf(node)
      sizes.set(node.id, {
        width: estimateNumberedBranchWidth(
          text,
          prefix,
          node.id,
          paintedStyle(node, box),
          box.shape
        ),
        height: branchHeight(node, text, prefix, box),
      })
    }
  })
  return sizes
}
