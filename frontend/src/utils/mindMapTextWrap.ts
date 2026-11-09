/**
 * Shared thinking-map label wrap contract (canvas hosts + vector PDF/DOCX export).
 *
 * Width comes from the browser when that measurement sits near the fallback
 * estimate. A label that fits the script-aware column stays one line. A longer
 * label wraps at the map's own cap. Han, kana, hangul, and fullwidth characters
 * are break points, matching canvas ``word-break: normal``, so a Latin word
 * such as ``AI`` or ``77%`` stays on the same line as the text that follows.
 */
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { onTextMeasureCacheClear } from '@/stores/specLoader/textMeasureCache'
import { measureCssWrappedBlockPx, measureTextWidth } from '@/stores/specLoader/textMeasurement'
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
  /**
   * Hard cap on the wrap column, in px. A node whose CSS max is tighter than
   * the script-aware column passes its content-box width here so the browser
   * and the stand-in wrap at the same edge.
   */
  columnCeiling?: number
}

function normalizeWeight(fontWeight?: string): 'normal' | 'bold' {
  return fontWeight === 'bold' || fontWeight === '700' ? 'bold' : 'normal'
}

function labelMeasureBand(
  text: string,
  fontSize: number,
  options: MindMapTextMeasureOptions
): {
  fontWeight: 'normal' | 'bold'
  fontFamily: string
  fallback: number
  measured: number | null
} {
  const fontWeight = normalizeWeight(options.fontWeight)
  const fontFamily = options.fontFamily ?? MIND_MAP_GEOMETRY.fontFamily
  const fallback = estimateTextWidthFallbackPx(text, fontSize, {
    isTopic: fontWeight === 'bold',
  })
  if (typeof document === 'undefined') {
    return { fontWeight, fontFamily, fallback, measured: null }
  }
  return {
    fontWeight,
    fontFamily,
    fallback,
    measured: measureTextWidth(text, fontSize, { fontWeight, fontFamily }),
  }
}

function browserMeasureAccepted(measured: number | null, fallback: number): boolean {
  return (
    measured != null && measured > 0 && measured >= fallback * 0.5 && measured <= fallback * 1.85
  )
}

/**
 * False when a real browser measured this label as missing or absurd.
 * jsdom and non-DOM runs stay true so the em fallback remains the layout box.
 */
export function isMindMapLabelMeasureTrusted(
  text: string,
  fontSize: number,
  options: MindMapTextMeasureOptions = {}
): boolean {
  const label = (text || '').trim()
  if (!label) return true
  if (typeof document === 'undefined') return true
  if (typeof navigator !== 'undefined' && /jsdom/i.test(navigator.userAgent)) return true
  const { fallback, measured } = labelMeasureBand(label, fontSize, options)
  return browserMeasureAccepted(measured, fallback)
}

/** Shared label advance (canvas estimate + vector export). */
export function measureMindMapLabelWidthPx(
  text: string,
  fontSize: number,
  options: MindMapTextMeasureOptions = {}
): number {
  if (!text) return 0
  const { fallback, measured } = labelMeasureBand(text, fontSize, options)
  // Reject flat/tiny jsdom widths; accept real browser metrics near the estimate.
  if (browserMeasureAccepted(measured, fallback) && measured != null) return measured
  return fallback
}

/**
 * Wrap column for any thinking-map label.
 * Fits the script-aware threshold → that threshold (one line).
 * Longer text → ``baseCapPx``.
 */
export function resolveThinkingMapTextColumnPx(
  text: string,
  fontSize: number,
  baseCapPx: number,
  options: MindMapTextMeasureOptions = {}
): number {
  const label = (text || '').trim()
  if (!label) return capColumn(baseCapPx, options.columnCeiling)
  const wrapThreshold = computeScriptAwareMaxWidth(label, baseCapPx)
  const textWidth = measureMindMapLabelWidthPx(label, fontSize, options)
  const column = textWidth <= wrapThreshold ? wrapThreshold : baseCapPx
  return capColumn(column, options.columnCeiling)
}

function capColumn(column: number, ceiling: number | undefined): number {
  if (ceiling == null || !Number.isFinite(ceiling) || ceiling <= 0) return column
  return Math.min(column, ceiling)
}

export type ThinkingMapLabelBlock = {
  width: number
  height: number
  lineCount: number
}

const LABEL_MEASURE_CACHE_MAX = 500
const displayMaxWidthCache = new Map<string, number>()
const labelBlockCache = new Map<string, ThinkingMapLabelBlock>()
onTextMeasureCacheClear(() => {
  displayMaxWidthCache.clear()
  labelBlockCache.clear()
})

function labelMeasureCacheKey(
  label: string,
  fontSize: number,
  baseCapPx: number,
  options: MindMapTextMeasureOptions
): string {
  return `${fontSize}\u0001${options.fontWeight ?? ''}\u0001${options.fontFamily ?? ''}\u0001${baseCapPx}\u0001${options.columnCeiling ?? ''}\u0001${label}`
}

function rememberLabelMeasure<T>(cache: Map<string, T>, key: string, value: T): void {
  if (cache.size >= LABEL_MEASURE_CACHE_MAX) {
    const oldest = cache.keys().next().value
    if (oldest !== undefined) cache.delete(oldest)
  }
  cache.set(key, value)
}

/**
 * Content box after the shared wrap. One line reports the measured width, not the threshold.
 * The wrap measures every candidate line, so a long label costs thousands of DOM reads.
 * Layouts that re-run on each node size report reuse the block until a font lands.
 */
export function measureThinkingMapLabelBlockPx(
  text: string,
  fontSize: number,
  baseCapPx: number,
  options: MindMapTextMeasureOptions = {}
): ThinkingMapLabelBlock {
  const label = (text || '').trim() || ' '
  const cacheKey = labelMeasureCacheKey(label, fontSize, baseCapPx, options)
  const cached = labelBlockCache.get(cacheKey)
  if (cached !== undefined) return cached
  const block = wrapThinkingMapLabelBlock(label, fontSize, baseCapPx, options)
  rememberLabelMeasure(labelBlockCache, cacheKey, block)
  return block
}

function wrapThinkingMapLabelBlock(
  label: string,
  fontSize: number,
  baseCapPx: number,
  options: MindMapTextMeasureOptions
): ThinkingMapLabelBlock {
  const column = resolveThinkingMapTextColumnPx(
    label === ' ' ? '' : label,
    fontSize,
    baseCapPx,
    options
  )
  const single = measureMindMapLabelWidthPx(label, fontSize, options)
  if (!label.includes('\n') && (label === ' ' || single <= column)) {
    return {
      width: single,
      height: fontSize * MIND_MAP_TEXT_LINE_HEIGHT,
      lineCount: 1,
    }
  }
  const lines = wrapMindMapTextLines(label, column, { fontSize, ...options })
  let width = 0
  for (const line of lines) {
    width = Math.max(width, measureMindMapLabelWidthPx(line, fontSize, options))
  }
  return {
    width: width > 0 ? width : Math.min(single, baseCapPx),
    height: Math.max(lines.length, 1) * fontSize * MIND_MAP_TEXT_LINE_HEIGHT,
    lineCount: Math.max(lines.length, 1),
  }
}

/**
 * CSS max-width. A one-line label gets the script-aware column.
 * A wrapped label gets the balanced line width, never wider than the cap.
 * Repeated calls with the same text and font reuse the width until a font lands,
 * so a column shift does not measure every label again.
 */
export function resolveThinkingMapDisplayMaxWidthPx(
  text: string,
  fontSize: number,
  baseCapPx: number,
  options: MindMapTextMeasureOptions = {}
): number {
  const label = (text || '').trim()
  if (!label) return baseCapPx
  const cacheKey = labelMeasureCacheKey(label, fontSize, baseCapPx, options)
  const cached = displayMaxWidthCache.get(cacheKey)
  if (cached !== undefined) return cached
  const column = resolveThinkingMapTextColumnPx(label, fontSize, baseCapPx, options)
  const block = measureThinkingMapLabelBlockPx(label, fontSize, baseCapPx, options)
  const width =
    block.lineCount <= 1 && !label.includes('\n')
      ? column
      : Math.max(8, Math.min(column, Math.ceil(block.width)))
  rememberLabelMeasure(displayMaxWidthCache, cacheKey, width)
  return width
}

/**
 * Canvas branch ``:max-width`` in px (same logic as MindMapV2/LegacyBranchNode).
 */
export function resolveMindMapBranchTextMaxWidthPx(
  label: string,
  fontSize: number,
  options: MindMapTextMeasureOptions = {}
): number {
  return resolveThinkingMapTextColumnPx(label, fontSize, MIND_MAP_BRANCH_MAX_TEXT_WIDTH, options)
}

/**
 * Mind map branch text box as painted. The branch ``max-width`` is the whole
 * column, so a wrapped branch fills it; other thinking maps paint at the tight
 * width from {@link measureThinkingMapLabelBlockPx}.
 */
export function measureMindMapBranchPaintedBlockPx(
  text: string,
  fontSize: number,
  options: MindMapTextMeasureOptions = {}
): ThinkingMapLabelBlock {
  const label = (text || '').trim()
  const column = resolveMindMapBranchTextMaxWidthPx(label, fontSize, options)
  const painted = measureCssWrappedBlockPx(label, fontSize, column, {
    fontWeight: options.fontWeight,
    fontFamily: options.fontFamily ?? MIND_MAP_GEOMETRY.fontFamily,
  })
  const lineHeightPx = fontSize * MIND_MAP_TEXT_LINE_HEIGHT
  if (painted) {
    const lineCount = Math.max(1, Math.round(painted.height / lineHeightPx) || 1)
    return { width: painted.width, height: lineCount * lineHeightPx, lineCount }
  }
  const block = measureThinkingMapLabelBlockPx(
    label,
    fontSize,
    MIND_MAP_BRANCH_MAX_TEXT_WIDTH,
    options
  )
  return block.lineCount > 1 ? { ...block, width: column } : block
}

export const MIND_MAP_NUMBER_PREFIX_GAP_PX = 6
const MIN_BRANCH_BODY_MAX_WIDTH_PX = 48

/** Advance of the painted prefix chrome (glyphs + gap before the body). */
export function measureMindMapNumberPrefixAdvancePx(
  prefix: string,
  fontSize: number,
  options: MindMapTextMeasureOptions = {}
): number {
  if (!prefix) return 0
  return measureMindMapLabelWidthPx(prefix, fontSize, options) + MIND_MAP_NUMBER_PREFIX_GAP_PX
}

/**
 * Content width of prefix chrome + body, using this node's actual prefix glyphs.
 * ``1.`` / ``①`` / ``第一章`` therefore produce different widths.
 */
export function estimateMindMapNumberedContentWidthPx(
  label: string,
  prefix: string,
  fontSize: number,
  options: MindMapTextMeasureOptions = {}
): number {
  const bodyWidth = measureMindMapLabelWidthPx((label || '').trim(), fontSize, options)
  if (!prefix) return bodyWidth
  return measureMindMapNumberPrefixAdvancePx(prefix, fontSize, options) + bodyWidth
}

/**
 * Wrap budget for the editable body when a numbering prefix sits beside it.
 * Keeps prefix + gap + body within the same column as an un-numbered label.
 */
export function resolveMindMapBranchBodyMaxWidthPx(
  label: string,
  prefix: string,
  fontSize: number,
  options: MindMapTextMeasureOptions = {}
): number {
  const totalMax = resolveMindMapBranchTextMaxWidthPx(
    prefix ? `${prefix} ${label}`.trim() : label,
    fontSize,
    options
  )
  if (!prefix) return totalMax
  const prefixAdvance = measureMindMapNumberPrefixAdvancePx(prefix, fontSize, options)
  return Math.max(MIN_BRANCH_BODY_MAX_WIDTH_PX, totalMax - prefixAdvance)
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
  if (
    !plain.includes('\n') &&
    measureMindMapLabelWidthPx(plain, options.fontSize, measureOpts) <= hostMax
  ) {
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

/**
 * CSS ``word-break: normal`` may break after these (Han, kana, hangul, fullwidth).
 * Latin words and numbers stay one token so ``AI`` and ``77%`` are not split.
 */
function isWrapBreakChar(codePoint: number): boolean {
  if (codePoint >= 0x1100 && codePoint <= 0x11ff) return true
  if (codePoint >= 0x3000 && codePoint <= 0x303f) return true
  if (codePoint >= 0x3040 && codePoint <= 0x30ff) return true
  if (codePoint >= 0x3130 && codePoint <= 0x318f) return true
  if (codePoint >= 0x31f0 && codePoint <= 0x31ff) return true
  if (codePoint >= 0x3400 && codePoint <= 0x9fff) return true
  if (codePoint >= 0xac00 && codePoint <= 0xd7af) return true
  if (codePoint >= 0xf900 && codePoint <= 0xfaff) return true
  if (codePoint >= 0xff00 && codePoint <= 0xffef) return true
  return false
}

function tokenizeForWrap(text: string): string[] {
  const tokens: string[] = []
  let word = ''
  const flushWord = () => {
    if (!word) return
    tokens.push(word)
    word = ''
  }
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0
    if (/\s/u.test(ch)) {
      flushWord()
      const prev = tokens[tokens.length - 1]
      if (prev && /^\s+$/u.test(prev)) tokens[tokens.length - 1] = prev + ch
      else tokens.push(ch)
      continue
    }
    if (isWrapBreakChar(cp)) {
      flushWord()
      tokens.push(ch)
      continue
    }
    word += ch
  }
  flushWord()
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

function placeToken(
  token: string,
  maxWidth: number,
  measure: (text: string) => number,
  lines: string[]
): string {
  if (!token) return ''
  if (measure(token) <= maxWidth) return token
  const broken = wrapLongToken(token, maxWidth, measure)
  lines.push(...broken.slice(0, -1))
  return broken[broken.length - 1] ?? ''
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
    if (/^\s+$/u.test(token)) {
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
      current = placeToken(token, maxWidth, measure, lines)
      continue
    }
    const candidate = current + token
    if (measure(candidate) <= maxWidth) {
      current = candidate
      continue
    }
    flush()
    current = placeToken(token, maxWidth, measure, lines)
  }
  flush()
  return lines.length > 0 ? lines : ['']
}

/**
 * Match canvas ``text-wrap: balance``: narrowest column that does not add a line.
 * Greedy wrap at the full column leaves one CJK glyph on the last line when the
 * text is only slightly wider than the column; balancing pulls that glyph up.
 */
function balanceParagraphLines(
  paragraph: string,
  maxWidth: number,
  measure: (text: string) => number
): string[] {
  const greedy = wrapParagraph(paragraph, maxWidth, measure)
  if (greedy.length < 2) return greedy
  let low = 8
  let high = Math.floor(maxWidth)
  let best = high
  while (low <= high) {
    const mid = Math.floor((low + high) / 2)
    const candidate = wrapParagraph(paragraph, mid, measure)
    if (candidate.length > greedy.length) {
      low = mid + 1
    } else {
      best = mid
      high = mid - 1
    }
  }
  const balanced = wrapParagraph(paragraph, best, measure)
  return balanced.length === greedy.length ? balanced : greedy
}

/**
 * Word-aware wrap approximating canvas CSS ``pre-wrap`` + ``word-break:normal``
 * + ``text-wrap: balance``.
 */
export function wrapMindMapTextLines(
  plain: string,
  maxWidth: number,
  options: MindMapWrapLinesOptions
): string[] {
  const width = Math.max(8, maxWidth)
  const fontSize = options.fontSize
  const measure = (text: string) =>
    measureMindMapLabelWidthPx(text, fontSize, {
      fontWeight: options.fontWeight,
      fontFamily: options.fontFamily,
    })
  const paragraphs = plain.replace(/\r\n/g, '\n').split('\n')
  const lines: string[] = []
  for (const paragraph of paragraphs) {
    lines.push(...balanceParagraphLines(paragraph, width, measure))
  }
  return lines.length > 0 ? lines : ['']
}
