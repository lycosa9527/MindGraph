/**
 * Shared mind-map label wrap contract (canvas hosts + vector PDF/DOCX export).
 *
 * Canvas SoT: InlineEditableText ``max-width`` + CSS
 * ``pre-wrap / word-break:normal / overflow-wrap:break-word / line-height:1.4``.
 * Export must use the same column width and the same break rules.
 */
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { measureTextWidth } from '@/stores/specLoader/textMeasurement'
import {
  computeScriptAwareMaxWidth,
  estimateTextWidthFallbackPx,
} from '@/stores/specLoader/textMeasurementFallback'

/** Branch InlineEditableText base maxWidth (px). */
export const MIND_MAP_BRANCH_MAX_TEXT_WIDTH = 200

/** Topic InlineEditableText maxWidth (px). */
export const MIND_MAP_TOPIC_MAX_TEXT_WIDTH = 300

/** Match ``.inline-edit-display`` / measure element. */
export const MIND_MAP_TEXT_LINE_HEIGHT = 1.4

/** Match underline + ``.diagram-node-md`` display. */
export const MIND_MAP_UNDERLINE_TEXT_LINE_HEIGHT = 1.35

export type MindMapTextWrapRole = 'topic' | 'branch'

export type MindMapTextMeasureOptions = {
  fontWeight?: 'normal' | 'bold' | string
  fontFamily?: string
}

function normalizeWeight(fontWeight?: string): 'normal' | 'bold' {
  return fontWeight === 'bold' || fontWeight === '700' ? 'bold' : 'normal'
}

function measureLabelWidth(
  text: string,
  fontSize: number,
  options: MindMapTextMeasureOptions = {}
): number {
  if (!text) return 0
  const fontWeight = normalizeWeight(options.fontWeight)
  const fontFamily = options.fontFamily ?? MIND_MAP_GEOMETRY.fontFamily
  const fallback = estimateTextWidthFallbackPx(text, fontSize, {
    isTopic: fontWeight === 'bold',
  })
  if (typeof document !== 'undefined') {
    const measured = measureTextWidth(text, fontSize, {
      fontWeight,
      fontFamily,
    })
    // Reject flat/tiny jsdom widths; accept real browser metrics near the estimate.
    if (measured > 0 && measured >= fallback * 0.5 && measured <= fallback * 1.85) {
      return measured
    }
  }
  return fallback
}

/**
 * Canvas branch ``:max-width`` in px (same logic as MindMapV2/LegacyBranchNode).
 */
export function resolveMindMapBranchTextMaxWidthPx(
  label: string,
  fontSize: number,
  options: MindMapTextMeasureOptions = {}
): number {
  const text = (label || '').trim()
  if (!text) return MIND_MAP_BRANCH_MAX_TEXT_WIDTH
  const wrapThreshold = computeScriptAwareMaxWidth(text, MIND_MAP_BRANCH_MAX_TEXT_WIDTH)
  const textWidth = measureLabelWidth(text, fontSize, options)
  if (textWidth <= wrapThreshold) {
    return wrapThreshold
  }
  return MIND_MAP_BRANCH_MAX_TEXT_WIDTH
}

/** Canvas topic ``:max-width`` in px. */
export function resolveMindMapTopicTextMaxWidthPx(): number {
  return MIND_MAP_TOPIC_MAX_TEXT_WIDTH
}

/**
 * Export wrap column: ``min(hostTextMaxWidth, boxInnerWidth)``.
 * Matches InlineEditableText (prop maxWidth + ``max-width: 100%`` of content box).
 */
export function resolveMindMapExportWrapColumnPx(options: {
  role: MindMapTextWrapRole
  text: string
  fontSize: number
  fontWeight?: 'normal' | 'bold' | string
  fontFamily?: string
  boxWidth: number
  paddingX: number
  borderWidth: number
}): number {
  const hostMax =
    options.role === 'topic'
      ? resolveMindMapTopicTextMaxWidthPx()
      : resolveMindMapBranchTextMaxWidthPx(options.text, options.fontSize, {
          fontWeight: options.fontWeight,
          fontFamily: options.fontFamily,
        })
  const boxInner = options.boxWidth - options.paddingX * 2 - options.borderWidth * 2
  if (!Number.isFinite(boxInner) || boxInner <= 0) {
    return Math.max(8, hostMax)
  }
  return Math.max(8, Math.min(hostMax, boxInner))
}

/**
 * Settled-canvas rule: if the label fits the host text maxWidth, keep one line
 * (the node grows). Only apply box-inner wrapping when the host would wrap.
 */
export function wrapMindMapExportLabelLines(options: {
  role: MindMapTextWrapRole
  text: string
  fontSize: number
  fontWeight?: 'normal' | 'bold' | string
  fontFamily?: string
  boxWidth: number
  paddingX: number
  borderWidth: number
}): string[] {
  const plain = options.text.replace(/\r\n/g, '\n')
  const measureOpts = {
    fontWeight: options.fontWeight,
    fontFamily: options.fontFamily ?? MIND_MAP_GEOMETRY.fontFamily,
  }
  const hostMax =
    options.role === 'topic'
      ? resolveMindMapTopicTextMaxWidthPx()
      : resolveMindMapBranchTextMaxWidthPx(plain, options.fontSize, measureOpts)

  // No manual newlines and text fits host column → canvas stays single-line.
  if (!plain.includes('\n') && measureLabelWidth(plain, options.fontSize, measureOpts) <= hostMax) {
    return [plain]
  }

  const column = resolveMindMapExportWrapColumnPx({
    role: options.role,
    text: plain,
    fontSize: options.fontSize,
    fontWeight: options.fontWeight,
    fontFamily: options.fontFamily,
    boxWidth: options.boxWidth,
    paddingX: options.paddingX,
    borderWidth: options.borderWidth,
  })
  return wrapMindMapTextLines(plain, column, {
    fontSize: options.fontSize,
    fontWeight: options.fontWeight,
    fontFamily: options.fontFamily ?? MIND_MAP_GEOMETRY.fontFamily,
  })
}

export type MindMapWrapLinesOptions = MindMapTextMeasureOptions & {
  fontSize: number
}

function tokenizeForWrap(text: string): string[] {
  const tokens: string[] = []
  const re =
    /(\s+)|([\u3400-\u9FFF\uF900-\uFAFF\u3000-\u303F\uFF00-\uFFEF]+)|([^\s\u3400-\u9FFF\uF900-\uFAFF\u3000-\u303F\uFF00-\uFFEF]+)/g
  let match: RegExpExecArray | null
  while ((match = re.exec(text)) !== null) {
    tokens.push(match[0])
  }
  return tokens
}

function wrapLongToken(
  token: string,
  maxWidth: number,
  measure: (text: string) => number
): string[] {
  const lines: string[] = []
  let current = ''
  for (const ch of token) {
    const next = current + ch
    if (current && measure(next) > maxWidth) {
      lines.push(current)
      current = ch
    } else {
      current = next
    }
  }
  if (current) lines.push(current)
  return lines.length > 0 ? lines : ['']
}

function wrapParagraph(
  paragraph: string,
  maxWidth: number,
  measure: (text: string) => number
): string[] {
  if (!paragraph) return ['']
  if (measure(paragraph) <= maxWidth) {
    return [paragraph]
  }
  const tokens = tokenizeForWrap(paragraph)
  const lines: string[] = []
  let current = ''
  const flush = () => {
    if (current) {
      lines.push(current)
      current = ''
    }
  }
  for (const token of tokens) {
    if (/^\s+$/.test(token)) {
      if (!current) continue
      const next = current + token
      if (measure(next) <= maxWidth) {
        current = next
      } else {
        flush()
      }
      continue
    }
    if (!current) {
      if (measure(token) <= maxWidth) {
        current = token
      } else {
        const broken = wrapLongToken(token, maxWidth, measure)
        lines.push(...broken.slice(0, -1))
        current = broken[broken.length - 1] ?? ''
      }
      continue
    }
    const candidate = current + token
    if (measure(candidate) <= maxWidth) {
      current = candidate
      continue
    }
    flush()
    if (measure(token) <= maxWidth) {
      current = token
    } else {
      const broken = wrapLongToken(token, maxWidth, measure)
      lines.push(...broken.slice(0, -1))
      current = broken[broken.length - 1] ?? ''
    }
  }
  flush()
  return lines.length > 0 ? lines : ['']
}

/**
 * Word-aware wrap approximating canvas CSS ``pre-wrap`` + ``word-break:normal``.
 */
export function wrapMindMapTextLines(
  plain: string,
  maxWidth: number,
  options: MindMapWrapLinesOptions
): string[] {
  const width = Math.max(8, maxWidth)
  const fontSize = options.fontSize
  const measure = (text: string) =>
    measureLabelWidth(text, fontSize, {
      fontWeight: options.fontWeight,
      fontFamily: options.fontFamily,
    })
  const paragraphs = plain.replace(/\r\n/g, '\n').split('\n')
  const lines: string[] = []
  for (const paragraph of paragraphs) {
    lines.push(...wrapParagraph(paragraph, width, measure))
  }
  return lines.length > 0 ? lines : ['']
}
