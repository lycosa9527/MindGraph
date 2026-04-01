/**
 * DOM-based text measurement for circle map nodes
 * Finds fontSize so text fits inside a circle (no truncation).
 * Wrap vs no-wrap uses prefersNoWrapWidthFitForCircleMap (Latin/Cyrillic vs CJK/Arabic/Thai…).
 *
 * Multi-flow / diagram labels with `$...$` math: use {@link measureRenderedDiagramLabelWidth}
 * so width matches KaTeX output (plain `measureTextWidth` measures LaTeX source as text).
 */
import {
  diagramLabelLikelyNeedsRenderedMeasure,
  isDiagramMarkdownPipelineLoaded,
  loadDiagramMarkdownPipeline,
  renderMarkdownForDiagramLabelMeasureSync,
} from '@/composables/core/diagramMarkdownPipeline'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

import {
  estimateTextWidthFallbackPx,
  prefersNoWrapWidthFitForCircleMap,
} from './textMeasurementFallback'

export { diagramLabelLikelyNeedsRenderedMeasure }

const MEASURE_FONT_FAMILY = DIAGRAM_NODE_FONT_STACK
const MIN_FONT_SIZE = 6
const TOPIC_DEFAULT_FONT_SIZE = 20
const CONTEXT_DEFAULT_FONT_SIZE = 14
const FONT_SIZE_STEP = 0.5
const MAX_WIDTH_OFFSET = 16
const BORDER_TOPIC = 3
const BORDER_CONTEXT = 2

/** Fixed font size for circle map context nodes (never change; grow circle instead). */
export const CONTEXT_FONT_SIZE = 14
/** Fixed font size for circle map topic node (never change; grow circle instead). */
export const TOPIC_FONT_SIZE = 18

/** Minimum radius for circle map topic (avoid too small when text is very short). */
const MIN_TOPIC_RADIUS_CIRCLE_MAP = 60
/** Inner padding inside topic circle (added after diagonal/2). */
const TOPIC_CIRCLE_INNER_PADDING = 10

let measureEl: HTMLDivElement | null = null
/** Separate from {@link measureEl} so KaTeX innerHTML does not break plain-text measurement. */
let diagramLabelHtmlMeasureEl: HTMLDivElement | null = null

function applyMeasureFontFamily(el: HTMLDivElement, fontFamily?: string): void {
  el.style.fontFamily = fontFamily ?? MEASURE_FONT_FAMILY
}

function getMeasureEl(fontFamily?: string): HTMLDivElement {
  if (measureEl && document.body.contains(measureEl)) {
    applyMeasureFontFamily(measureEl, fontFamily)
    return measureEl
  }
  measureEl = document.createElement('div')
  measureEl.setAttribute('aria-hidden', 'true')
  measureEl.style.cssText = [
    'position:absolute',
    'left:-9999px',
    'top:0',
    'visibility:hidden',
    'pointer-events:none',
    'white-space:pre-wrap',
    'word-break:break-word',
    'overflow-wrap:break-word',
    'text-align:center',
    'line-height:1.4',
    'box-sizing:border-box',
  ].join(';')
  applyMeasureFontFamily(measureEl, fontFamily)
  document.body.appendChild(measureEl)
  return measureEl
}

/**
 * Await `document.fonts.ready` so Canvas/TextMeasure uses loaded @font-face metrics.
 * Prefer {@link ensureFontsForLanguageCode} from `@/fonts/promptLanguageFonts` for diagram work:
 * it loads script Fontsource chunks for the prompt language and already awaits `fonts.ready` at the end.
 * Use this helper only when you need `fonts.ready` without a language-specific load (rare).
 */
export async function prepareDiagramTextMeasurement(): Promise<void> {
  if (typeof document === 'undefined' || !document.fonts?.ready) {
    return
  }
  try {
    await document.fonts.ready
  } catch {
    /* ignore */
  }
}

export interface MeasureTextFitOptions {
  /** Circle diameter in px */
  diameterPx: number
  /** Topic (bold) vs context (normal) */
  isTopic: boolean
  /** Font size to try (default: theme default) */
  fontSize?: number
  /** Optional override; defaults to diagram multiscript stack */
  fontFamily?: string
}

/**
 * True when text is mostly ASCII (English, digits, common punct.); use no-wrap + width-based fit.
 * @deprecated Prefer prefersNoWrapWidthFitForCircleMap for circle-map routing; kept for callers/tests.
 */
export function isMostlyAscii(text: string): boolean {
  const t = (text || '').trim()
  if (!t.length) return false
  let ascii = 0
  for (let i = 0; i < t.length; i++) {
    if (t.charCodeAt(i) < 128) ascii++
  }
  return ascii / t.length >= 0.8
}

export { prefersNoWrapWidthFitForCircleMap }

/**
 * Single-line labels: nowrap when measured width (+ padding) fits within maxWidthPx. Uses diagram font stack.
 */
export function shouldPreferSingleLineNoWrap(
  text: string,
  maxWidthPx: number,
  fontSizePx: number,
  options?: {
    fontWeight?: string
    horizontalPaddingPx?: number
    fontFamily?: string
  }
): boolean {
  const pad = options?.horizontalPaddingPx ?? 8
  const w = measureTextWidth(text || ' ', fontSizePx, {
    fontWeight: options?.fontWeight ?? 'normal',
    fontFamily: options?.fontFamily,
  })
  return w + pad <= maxWidthPx
}

/**
 * Measure if text fits in circle at given fontSize.
 * Uses effective box: width = diameter - 16 - 2*border, height limit = diameter - 2*border.
 */
export function measureTextFitsInCircle(
  text: string,
  options: MeasureTextFitOptions
): { fits: boolean; height: number } {
  if (typeof document === 'undefined') {
    return { fits: true, height: 0 }
  }
  const {
    diameterPx,
    isTopic,
    fontSize = isTopic ? TOPIC_DEFAULT_FONT_SIZE : CONTEXT_DEFAULT_FONT_SIZE,
    fontFamily,
  } = options
  const border = isTopic ? BORDER_TOPIC : BORDER_CONTEXT
  const effectiveHeight = diameterPx - 2 * border
  const maxW = Math.max(1, diameterPx - MAX_WIDTH_OFFSET - 2 * border)
  const t = (text || '').trim() || ' '
  const el = getMeasureEl(fontFamily)
  el.style.width = `${maxW}px`
  el.style.whiteSpace = 'pre-wrap'
  el.style.padding = isTopic ? '8px 12px' : '4px 8px'
  el.style.fontSize = `${fontSize}px`
  el.style.fontWeight = isTopic ? 'bold' : 'normal'
  el.textContent = t
  const height = el.offsetHeight
  const fits = height <= effectiveHeight
  return { fits, height }
}

export interface MeasureTextWidthOptions {
  /** Font weight (e.g. 'normal', 'bold'). Default 'normal'. */
  fontWeight?: string
  /** Optional override; defaults to diagram multiscript stack */
  fontFamily?: string
}

/**
 * Measure width of text in single line (no-wrap) at given fontSize.
 * Exported for use in overlays (e.g. learning sheet answer chips).
 */
export function measureTextWidth(
  text: string,
  fontSize: number,
  options?: MeasureTextWidthOptions
): number {
  if (typeof document === 'undefined') return 0
  const t = (text || '').trim() || ' '
  const el = getMeasureEl(options?.fontFamily)
  el.style.width = 'max-content'
  el.style.whiteSpace = 'nowrap'
  el.style.padding = '0'
  el.style.fontSize = `${fontSize}px`
  el.style.fontWeight = options?.fontWeight ?? 'normal'
  el.textContent = t
  return el.offsetWidth
}

function getDiagramLabelHtmlMeasureEl(fontFamily?: string): HTMLDivElement {
  if (diagramLabelHtmlMeasureEl && document.body.contains(diagramLabelHtmlMeasureEl)) {
    applyMeasureFontFamily(diagramLabelHtmlMeasureEl, fontFamily)
    return diagramLabelHtmlMeasureEl
  }
  diagramLabelHtmlMeasureEl = document.createElement('div')
  diagramLabelHtmlMeasureEl.setAttribute('aria-hidden', 'true')
  diagramLabelHtmlMeasureEl.style.cssText = [
    'position:absolute',
    'left:-9999px',
    'top:0',
    'visibility:hidden',
    'pointer-events:none',
    'box-sizing:content-box',
  ].join(';')
  applyMeasureFontFamily(diagramLabelHtmlMeasureEl, fontFamily)
  document.body.appendChild(diagramLabelHtmlMeasureEl)
  return diagramLabelHtmlMeasureEl
}

/** Strip a single outer `<p>...</p>` from markdown-it so width is inline-sized like diagram labels. */
function unwrapSingleParagraphHtml(html: string): string {
  const t = html.trim()
  const m = /^<p>([\s\S]*)<\/p>\s*$/i.exec(t)
  return m ? m[1] : t
}

/**
 * Measure label width after the same markdown + KaTeX pipeline as diagram nodes.
 * Use for multi-flow map column width when DOM dimensions are not yet available.
 */
export function measureRenderedDiagramLabelWidth(
  text: string,
  fontSizePx: number,
  options?: MeasureTextWidthOptions
): number {
  if (typeof document === 'undefined') {
    return estimateTextWidthFallbackPx(text || ' ', fontSizePx)
  }
  const t = (text || '').trim() || ' '
  const el = getDiagramLabelHtmlMeasureEl(options?.fontFamily)
  el.style.width = 'max-content'
  el.style.maxWidth = 'none'
  el.style.whiteSpace = 'nowrap'
  el.style.padding = '0'
  el.style.margin = '0'
  el.style.fontSize = `${fontSizePx}px`
  el.style.fontWeight = options?.fontWeight ?? 'normal'
  el.style.display = 'inline-block'
  el.style.lineHeight = '1.4'
  try {
    if (!diagramLabelLikelyNeedsRenderedMeasure(t)) {
      el.textContent = t
      void el.offsetWidth
      return Math.max(0, Math.ceil(el.getBoundingClientRect().width || el.offsetWidth))
    }
    if (!isDiagramMarkdownPipelineLoaded()) {
      void loadDiagramMarkdownPipeline()
      el.textContent = t
      void el.offsetWidth
      return Math.max(0, Math.ceil(el.getBoundingClientRect().width || el.offsetWidth))
    }
    let html: string
    try {
      html = unwrapSingleParagraphHtml(renderMarkdownForDiagramLabelMeasureSync(t))
    } catch {
      el.textContent = t
      void el.offsetWidth
      return el.offsetWidth
    }
    el.innerHTML = html
    void el.offsetWidth
    const w = el.getBoundingClientRect().width || el.offsetWidth
    return Math.max(0, Math.ceil(w))
  } finally {
    el.innerHTML = ''
    el.textContent = ''
  }
}

/**
 * Measure label height after the same markdown + KaTeX pipeline as diagram nodes.
 * The hidden element gets the `diagram-node-md` class so global KaTeX overrides
 * (inline-flex centering, line-height) apply, matching actual node rendering.
 *
 * @param maxTextWidthPx  max-width for the text content (triggers wrapping).
 */
export function measureRenderedDiagramLabelHeight(
  text: string,
  fontSizePx: number,
  maxTextWidthPx: number,
  options?: MeasureTextWidthOptions
): number {
  if (typeof document === 'undefined') {
    return fontSizePx * 1.5
  }
  const t = (text || '').trim() || ' '
  const el = getDiagramLabelHtmlMeasureEl(options?.fontFamily)
  el.style.width = 'max-content'
  el.style.maxWidth = `${maxTextWidthPx}px`
  el.style.whiteSpace = 'normal'
  el.style.padding = '0'
  el.style.margin = '0'
  el.style.fontSize = `${fontSizePx}px`
  el.style.fontWeight = options?.fontWeight ?? 'normal'
  el.style.display = 'inline-block'
  el.style.lineHeight = '1.35'
  el.className = 'diagram-node-md'
  try {
    if (!diagramLabelLikelyNeedsRenderedMeasure(t)) {
      el.textContent = t
      void el.offsetHeight
      return Math.max(0, el.getBoundingClientRect().height || el.offsetHeight)
    }
    if (!isDiagramMarkdownPipelineLoaded()) {
      void loadDiagramMarkdownPipeline()
      el.textContent = t
      void el.offsetHeight
      return Math.max(0, el.getBoundingClientRect().height || el.offsetHeight)
    }
    let html: string
    try {
      html = renderMarkdownForDiagramLabelMeasureSync(t)
    } catch {
      el.textContent = t
      void el.offsetHeight
      return el.offsetHeight
    }
    el.innerHTML = html
    void el.offsetHeight
    const measured = Math.max(0, el.getBoundingClientRect().height || el.offsetHeight)
    return measured
  } finally {
    el.innerHTML = ''
    el.textContent = ''
    el.className = ''
  }
}

export interface MeasureTextDimensionsOptions {
  /** Max width for wrapping (multi-line). If set, text wraps and height is measured. */
  maxWidth?: number
  /** Horizontal padding (each side). Default 16 (matches px-4). */
  paddingX?: number
  /** Vertical padding (each side). Default 8 (matches py-2). */
  paddingY?: number
  /** Font weight. Default 'normal'. */
  fontWeight?: string
  /** Optional override; defaults to diagram multiscript stack */
  fontFamily?: string
}

/**
 * Measure text dimensions (width and height) for layout.
 * With maxWidth: text wraps, returns actual width and height.
 * Without maxWidth: single-line, width from content, height from line-height.
 */
export function measureTextDimensions(
  text: string,
  fontSize: number,
  options?: MeasureTextDimensionsOptions
): { width: number; height: number } {
  if (typeof document === 'undefined') {
    const w = estimateTextWidthFallbackPx(text, fontSize, {
      isTopic: (options?.fontWeight ?? 'normal') === 'bold',
    })
    const h = fontSize * 1.4 + (options?.paddingY ?? 8) * 2
    return { width: w + (options?.paddingX ?? 16) * 2, height: h }
  }
  const t = (text || '').trim() || ' '
  const paddingX = options?.paddingX ?? 16
  const paddingY = options?.paddingY ?? 8
  const el = getMeasureEl(options?.fontFamily)
  el.style.fontSize = `${fontSize}px`
  el.style.fontWeight = options?.fontWeight ?? 'normal'
  el.style.padding = `${paddingY}px ${paddingX}px`
  el.style.lineHeight = '1.4'
  if (options?.maxWidth != null) {
    el.style.maxWidth = `${options.maxWidth}px`
    el.style.width = 'max-content'
    el.style.whiteSpace = 'pre-wrap'
    el.style.wordBreak = 'break-word'
  } else {
    el.style.width = 'max-content'
    el.style.whiteSpace = 'nowrap'
  }
  el.textContent = t
  const width = el.offsetWidth
  const height = el.offsetHeight
  return { width, height }
}

function measureTextWidthNoWrap(
  text: string,
  options: { isTopic: boolean; fontSize: number; fontFamily?: string }
): number {
  if (typeof document === 'undefined') return 0
  const t = (text || '').trim() || ' '
  const el = getMeasureEl(options.fontFamily)
  el.style.width = 'max-content'
  el.style.whiteSpace = 'nowrap'
  el.style.padding = options.isTopic ? '8px 12px' : '4px 8px'
  el.style.fontSize = `${options.fontSize}px`
  el.style.fontWeight = options.isTopic ? 'bold' : 'normal'
  el.textContent = t
  return el.offsetWidth
}

/**
 * Minimum diameter (px) so that text fits in one line at fixed fontSize (no-wrap).
 * Used by circle map: fixed font, grow circle to fit. Padding matches layout (MAX_WIDTH_OFFSET, BORDER_*).
 */
export function computeMinDiameterForNoWrap(
  text: string,
  fontSize: number,
  isTopic: boolean
): number {
  if (typeof document === 'undefined') {
    return fallbackMinDiameterForNoWrap(text, fontSize, isTopic)
  }
  const border = isTopic ? BORDER_TOPIC : BORDER_CONTEXT
  const w = measureTextWidthNoWrap(text, { isTopic, fontSize })
  return Math.ceil(w + MAX_WIDTH_OFFSET + 2 * border)
}

function fallbackMinDiameterForNoWrap(text: string, fontSize: number, isTopic: boolean): number {
  const len = (text || '').trim().length
  if (len === 0) return isTopic ? 120 : 70
  const border = isTopic ? BORDER_TOPIC : BORDER_CONTEXT
  const w = estimateTextWidthFallbackPx(text, fontSize, { isTopic }) + (isTopic ? 24 : 16)
  return Math.ceil(w + MAX_WIDTH_OFFSET + 2 * border)
}

/**
 * Find max fontSize such that no-wrap text fits in circle (width-based).
 */
export function computeFontSizeToFitCircleNoWrap(
  text: string,
  diameterPx: number,
  isTopic: boolean
): number {
  if (typeof document === 'undefined') {
    return fallbackFontSizeToFitNoWrap(text, diameterPx, isTopic)
  }
  const border = isTopic ? BORDER_TOPIC : BORDER_CONTEXT
  const effectiveWidth = Math.max(1, diameterPx - MAX_WIDTH_OFFSET - 2 * border)
  const maxFs = isTopic ? TOPIC_DEFAULT_FONT_SIZE : CONTEXT_DEFAULT_FONT_SIZE
  let low = MIN_FONT_SIZE
  let high = maxFs
  let best = MIN_FONT_SIZE
  const step = FONT_SIZE_STEP
  while (high - low >= step) {
    const mid = (low + high) / 2
    const w = measureTextWidthNoWrap(text, { isTopic, fontSize: mid })
    if (w <= effectiveWidth) {
      best = mid
      low = mid + step
    } else {
      high = mid - step
    }
  }
  return Math.round(best * 10) / 10
}

/**
 * Find max fontSize such that text fits in circle (DOM measurement).
 * Wrap mode: fit by height. Use computeFontSizeToFitCircleNoWrap for word-separated scripts.
 */
export function computeFontSizeToFitCircle(
  text: string,
  diameterPx: number,
  isTopic: boolean
): number {
  if (typeof document === 'undefined') {
    return fallbackFontSizeToFit(text, diameterPx, isTopic)
  }
  const maxFs = isTopic ? TOPIC_DEFAULT_FONT_SIZE : CONTEXT_DEFAULT_FONT_SIZE
  let low = MIN_FONT_SIZE
  let high = maxFs
  let best = MIN_FONT_SIZE
  const step = FONT_SIZE_STEP
  while (high - low >= step) {
    const mid = (low + high) / 2
    const { fits } = measureTextFitsInCircle(text, { diameterPx, isTopic, fontSize: mid })
    if (fits) {
      best = mid
      low = mid + step
    } else {
      high = mid - step
    }
  }
  return Math.round(best * 10) / 10
}

/**
 * Uniform context fontSize: min over all context texts so longest fits.
 * No-wrap width fit for Latin/Cyrillic/ASCII; wrap height fit for CJK, Arabic, Hebrew, Thai…
 */
export function computeContextFontSize(texts: string[], uniformContextDiameterPx: number): number {
  if (!texts.length) return CONTEXT_DEFAULT_FONT_SIZE
  let minFs = CONTEXT_DEFAULT_FONT_SIZE
  for (const t of texts) {
    const fs = prefersNoWrapWidthFitForCircleMap(t)
      ? computeFontSizeToFitCircleNoWrap(t, uniformContextDiameterPx, false)
      : computeFontSizeToFitCircle(t, uniformContextDiameterPx, false)
    minFs = Math.min(minFs, fs)
  }
  return Math.max(MIN_FONT_SIZE, minFs)
}

function fallbackFontSizeToFit(text: string, diameterPx: number, isTopic: boolean): number {
  const inner = Math.max(1, diameterPx - MAX_WIDTH_OFFSET - 24)
  const lineHeight = 1.4
  const t = (text || '').trim() || ' '
  const approxW = estimateTextWidthFallbackPx(t, 14, { isTopic })
  const approxLines = Math.max(1, Math.ceil(approxW / inner))
  const maxFontSizeByHeight = (diameterPx - 24) / (approxLines * lineHeight)
  const maxFs = isTopic ? TOPIC_DEFAULT_FONT_SIZE : CONTEXT_DEFAULT_FONT_SIZE
  const fs = Math.min(maxFs, maxFontSizeByHeight)
  return Math.max(MIN_FONT_SIZE, Math.floor(fs))
}

function fallbackFontSizeToFitNoWrap(text: string, diameterPx: number, isTopic: boolean): number {
  const trimmed = (text || '').trim()
  if (!trimmed.length) return isTopic ? TOPIC_DEFAULT_FONT_SIZE : CONTEXT_DEFAULT_FONT_SIZE
  const border = isTopic ? BORDER_TOPIC : BORDER_CONTEXT
  const effectiveWidth = diameterPx - MAX_WIDTH_OFFSET - 2 * border - (isTopic ? 24 : 16)
  const maxFs = isTopic ? TOPIC_DEFAULT_FONT_SIZE : CONTEXT_DEFAULT_FONT_SIZE
  const wAtMax = estimateTextWidthFallbackPx(trimmed, maxFs, { isTopic })
  if (wAtMax <= 0) return maxFs
  const fs = (effectiveWidth / wAtMax) * maxFs
  return Math.max(MIN_FONT_SIZE, Math.min(maxFs, Math.floor(fs)))
}

function measureTextWithSVG(
  text: string,
  fontSize: number,
  isTopic: boolean,
  fontFamily?: string
): { width: number; height: number } {
  if (typeof document === 'undefined') {
    const w = estimateTextWidthFallbackPx(text, fontSize, { isTopic })
    const approxCharHeight = fontSize * 1.4
    return {
      width: w,
      height: approxCharHeight,
    }
  }

  const el = getMeasureEl(fontFamily)
  el.style.width = 'max-content'
  el.style.whiteSpace = 'nowrap'
  el.style.fontSize = `${fontSize}px`
  el.style.fontWeight = isTopic ? 'bold' : 'normal'
  el.style.padding = '0'
  el.style.lineHeight = '1.4'
  el.style.boxSizing = 'content-box'
  el.textContent = text.trim()

  const width = el.offsetWidth || 0
  const height = el.offsetHeight || fontSize * 1.4

  return {
    width,
    height,
  }
}

/**
 * Calculate bubble map node radius based on text length
 * Uses DOM measurement and diagonal calculation
 * as per BUBBLE_MAP_TEXT_ADAPTATION.md and BUBBLE_MAP_SIZE_CALCULATION.md
 *
 * Formula: radius = sqrt(width² + height²) / 2 + padding
 */
export function calculateBubbleMapRadius(
  text: string,
  fontSize: number = CONTEXT_DEFAULT_FONT_SIZE,
  padding: number = 10,
  minRadius: number = 30,
  isTopic: boolean = false
): number {
  if (!text || !text.trim()) {
    return minRadius
  }

  const { width, height } = measureTextWithSVG(text.trim(), fontSize, isTopic)

  const measuredWidth = width || estimateTextWidthFallbackPx(text, fontSize, { isTopic })
  const measuredHeight = height || fontSize * 1.4

  const diagonal = Math.sqrt(measuredWidth * measuredWidth + measuredHeight * measuredHeight)
  const radius = Math.ceil(diagonal / 2 + padding)

  return Math.max(minRadius, radius)
}

const DOUBLE_BUBBLE_MIN_TOPIC_RADIUS = 32
const DOUBLE_BUBBLE_MIN_SIM_RADIUS = 24
const DOUBLE_BUBBLE_MIN_DIFF_RADIUS = 24
const DOUBLE_BUBBLE_TOPIC_PADDING = 12
const DOUBLE_BUBBLE_SIM_PADDING = 5
const DOUBLE_BUBBLE_DIFF_PADDING = 5

export function doubleBubbleRequiredRadius(
  text: string,
  options: {
    isTopic: boolean
    savedRadius?: number
  }
): number {
  const { isTopic, savedRadius } = options
  const trimmed = (text || '').trim()
  if (!trimmed) {
    if (savedRadius != null && savedRadius > 0) return savedRadius
    return isTopic ? DOUBLE_BUBBLE_MIN_TOPIC_RADIUS : DOUBLE_BUBBLE_MIN_SIM_RADIUS
  }
  const fontSize = isTopic ? TOPIC_FONT_SIZE : CONTEXT_FONT_SIZE
  const padding = isTopic ? DOUBLE_BUBBLE_TOPIC_PADDING : DOUBLE_BUBBLE_SIM_PADDING
  const minR = isTopic ? DOUBLE_BUBBLE_MIN_TOPIC_RADIUS : DOUBLE_BUBBLE_MIN_SIM_RADIUS
  return calculateBubbleMapRadius(trimmed, fontSize, padding, minR, isTopic)
}

export function doubleBubbleDiffRequiredRadius(text: string, savedRadius?: number): number {
  const trimmed = (text || '').trim()
  if (!trimmed) {
    if (savedRadius != null && savedRadius > 0) return savedRadius
    return DOUBLE_BUBBLE_MIN_DIFF_RADIUS
  }
  return calculateBubbleMapRadius(
    trimmed,
    CONTEXT_FONT_SIZE,
    DOUBLE_BUBBLE_DIFF_PADDING,
    DOUBLE_BUBBLE_MIN_DIFF_RADIUS,
    false
  )
}

export function computeTopicRadiusForCircleMap(text: string): number {
  const t = (text || '').trim() || ' '
  if (typeof document === 'undefined') {
    const approxW = estimateTextWidthFallbackPx(t, TOPIC_FONT_SIZE, { isTopic: true })
    const approxH = TOPIC_FONT_SIZE * 1.4
    const diagonal = Math.sqrt(approxW * approxW + approxH * approxH)
    const contentR = Math.ceil(diagonal / 2 + TOPIC_CIRCLE_INNER_PADDING)
    return Math.max(MIN_TOPIC_RADIUS_CIRCLE_MAP, contentR + BORDER_TOPIC)
  }
  const { width, height } = measureTextWithSVG(t, TOPIC_FONT_SIZE, true)
  const w = width || estimateTextWidthFallbackPx(t, TOPIC_FONT_SIZE, { isTopic: true })
  const h = height || TOPIC_FONT_SIZE * 1.4
  const diagonal = Math.sqrt(w * w + h * h)
  const contentR = Math.ceil(diagonal / 2 + TOPIC_CIRCLE_INNER_PADDING)
  const radius = contentR + BORDER_TOPIC
  return Math.max(MIN_TOPIC_RADIUS_CIRCLE_MAP, radius)
}
