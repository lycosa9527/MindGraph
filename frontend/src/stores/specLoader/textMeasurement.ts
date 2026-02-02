/**
 * DOM-based text measurement for circle map nodes
 * Finds fontSize so text fits inside a circle (no truncation).
 * Supports wrap (CJK) and no-wrap (English/numbers); no-wrap fits by width.
 */

const FONT_FAMILY = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
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

function getMeasureEl(): HTMLDivElement {
  if (measureEl && document.body.contains(measureEl)) {
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
  measureEl.style.fontFamily = FONT_FAMILY
  document.body.appendChild(measureEl)
  return measureEl
}

export interface MeasureTextFitOptions {
  /** Circle diameter in px */
  diameterPx: number
  /** Topic (bold) vs context (normal) */
  isTopic: boolean
  /** Font size to try (default: theme default) */
  fontSize?: number
}

/**
 * True when text is mostly ASCII (English, digits, common punct.); use no-wrap + width-based fit.
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
  const { diameterPx, isTopic, fontSize = isTopic ? TOPIC_DEFAULT_FONT_SIZE : CONTEXT_DEFAULT_FONT_SIZE } = options
  const border = isTopic ? BORDER_TOPIC : BORDER_CONTEXT
  const effectiveHeight = diameterPx - 2 * border
  const maxW = Math.max(1, diameterPx - MAX_WIDTH_OFFSET - 2 * border)
  const t = (text || '').trim() || ' '
  const el = getMeasureEl()
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

/**
 * Measure width of text in single line (no-wrap) at given fontSize.
 */
function measureTextWidthNoWrap(
  text: string,
  options: { isTopic: boolean; fontSize: number }
): number {
  if (typeof document === 'undefined') return 0
  const t = (text || '').trim() || ' '
  const el = getMeasureEl()
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
  const approxCharWidth = isTopic ? 0.6 : 0.55
  const w = len * fontSize * approxCharWidth + (isTopic ? 24 : 16)
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
 * Wrap mode: fit by height. Use computeFontSizeToFitCircleNoWrap for English/no-wrap.
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
 * Uses no-wrap (width) for mostly-ASCII, wrap (height) otherwise.
 */
export function computeContextFontSize(texts: string[], uniformContextDiameterPx: number): number {
  if (!texts.length) return CONTEXT_DEFAULT_FONT_SIZE
  let minFs = CONTEXT_DEFAULT_FONT_SIZE
  for (const t of texts) {
    const fs = isMostlyAscii(t)
      ? computeFontSizeToFitCircleNoWrap(t, uniformContextDiameterPx, false)
      : computeFontSizeToFitCircle(t, uniformContextDiameterPx, false)
    minFs = Math.min(minFs, fs)
  }
  return Math.max(MIN_FONT_SIZE, minFs)
}

function fallbackFontSizeToFit(text: string, diameterPx: number, isTopic: boolean): number {
  const len = (text || '').trim().length
  const inner = Math.max(1, diameterPx - MAX_WIDTH_OFFSET - 24)
  const approxCharWidth = isTopic ? 0.55 : 0.5
  const approxLines = Math.max(1, Math.ceil((len * approxCharWidth * 14) / inner))
  const lineHeight = 1.4
  const maxFontSizeByHeight = (diameterPx - 24) / (approxLines * lineHeight)
  const maxFs = isTopic ? TOPIC_DEFAULT_FONT_SIZE : CONTEXT_DEFAULT_FONT_SIZE
  const fs = Math.min(maxFs, maxFontSizeByHeight)
  return Math.max(MIN_FONT_SIZE, Math.floor(fs))
}

function fallbackFontSizeToFitNoWrap(text: string, diameterPx: number, isTopic: boolean): number {
  const len = (text || '').trim().length
  if (len === 0) return isTopic ? TOPIC_DEFAULT_FONT_SIZE : CONTEXT_DEFAULT_FONT_SIZE
  const border = isTopic ? BORDER_TOPIC : BORDER_CONTEXT
  const effectiveWidth = diameterPx - MAX_WIDTH_OFFSET - 2 * border - (isTopic ? 24 : 16)
  const approxCharWidth = isTopic ? 0.6 : 0.55
  const maxFs = isTopic ? TOPIC_DEFAULT_FONT_SIZE : CONTEXT_DEFAULT_FONT_SIZE
  const fs = effectiveWidth / (len * approxCharWidth)
  return Math.max(MIN_FONT_SIZE, Math.min(maxFs, Math.floor(fs)))
}

/**
 * Measure text dimensions using SVG getBBox() method (as per documentation)
 * This provides the most accurate measurement for text rendering
 * @param text - Text content
 * @param fontSize - Font size in pixels
 * @param isTopic - Whether this is a topic node (affects font weight)
 * @returns Object with width and height in pixels
 */
function measureTextWithSVG(
  text: string,
  fontSize: number,
  isTopic: boolean
): { width: number; height: number } {
  if (typeof document === 'undefined') {
    // Fallback: estimate dimensions
    const len = text.trim().length
    const approxCharWidth = fontSize * (isTopic ? 0.6 : 0.55)
    const approxCharHeight = fontSize * 1.4
    return {
      width: len * approxCharWidth,
      height: approxCharHeight,
    }
  }

  // Use DOM measurement (consistent with project patterns, more reliable)
  // Reference documentation: measure text width and height, use diagonal to calculate radius
  const el = getMeasureEl()
  el.style.width = 'max-content'
  el.style.whiteSpace = 'nowrap' // Ensure single line display (per documentation)
  el.style.fontSize = `${fontSize}px`
  el.style.fontWeight = isTopic ? 'bold' : 'normal'
  el.style.fontFamily = FONT_FAMILY
  el.style.padding = '0'
  el.style.lineHeight = '1.4'
  el.style.boxSizing = 'content-box'
  el.textContent = text.trim()
  
  // Measure width and height
  const width = el.offsetWidth || 0
  const height = el.offsetHeight || fontSize * 1.4
  
  return {
    width,
    height,
  }
}

/**
 * Calculate bubble map node radius based on text length
 * Uses SVG getBBox() for accurate measurement and diagonal calculation
 * as per BUBBLE_MAP_TEXT_ADAPTATION.md and BUBBLE_MAP_SIZE_CALCULATION.md
 * 
 * Formula: radius = sqrt(width² + height²) / 2 + padding
 * 
 * @param text - Text content
 * @param fontSize - Font size to use for measurement
 * @param padding - Padding around text (default: 10 for attributes, 20 for topic)
 * @param minRadius - Minimum radius (default: 30)
 * @param isTopic - Whether this is a topic node (affects font weight)
 * @returns Radius in pixels
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

  // Measure text dimensions (width and height)
  const { width, height } = measureTextWithSVG(text.trim(), fontSize, isTopic)

  // If measurement fails (width/height is 0), use estimated values
  const measuredWidth = width || text.trim().length * fontSize * (isTopic ? 0.6 : 0.55)
  const measuredHeight = height || fontSize * 1.4

  // Calculate radius using diagonal: sqrt(width² + height²) / 2 + padding
  // Per documentation BUBBLE_MAP_SIZE_CALCULATION.md requirements
  const diagonal = Math.sqrt(measuredWidth * measuredWidth + measuredHeight * measuredHeight)
  const radius = Math.ceil(diagonal / 2 + padding)

  return Math.max(minRadius, radius)
}

// Double bubble map: min radii and paddings per type (topic / similarity / difference); tight text fit, small inner padding
const DOUBLE_BUBBLE_MIN_TOPIC_RADIUS = 32
const DOUBLE_BUBBLE_MIN_SIM_RADIUS = 24
const DOUBLE_BUBBLE_MIN_DIFF_RADIUS = 24
const DOUBLE_BUBBLE_TOPIC_PADDING = 12
const DOUBLE_BUBBLE_SIM_PADDING = 5
const DOUBLE_BUBBLE_DIFF_PADDING = 5

/**
 * Required radius for one double-bubble node: measure text → diagonal/2 + padding; empty node uses saved radius.
 * Measure text → calculate radius; empty node uses saved radius.
 */
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

/** Required radius for difference node (left/right); empty uses savedRadius. */
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

/**
 * Circle map center (topic) radius from text: measure text at same font/size as render,
 * use bounding box → radius = diagonal/2 + inner padding, with minimum radius.
 * Uses invisible DOM measurement for accurate width/height.
 *
 * @param text - Topic text
 * @returns Radius in pixels
 */
export function computeTopicRadiusForCircleMap(text: string): number {
  const t = (text || '').trim() || ' '
  if (typeof document === 'undefined') {
    const len = t.length
    const approxW = len * TOPIC_FONT_SIZE * 0.6
    const approxH = TOPIC_FONT_SIZE * 1.4
    const diagonal = Math.sqrt(approxW * approxW + approxH * approxH)
    return Math.max(MIN_TOPIC_RADIUS_CIRCLE_MAP, Math.ceil(diagonal / 2 + TOPIC_CIRCLE_INNER_PADDING))
  }
  const { width, height } = measureTextWithSVG(t, TOPIC_FONT_SIZE, true)
  const w = width || t.length * TOPIC_FONT_SIZE * 0.6
  const h = height || TOPIC_FONT_SIZE * 1.4
  const diagonal = Math.sqrt(w * w + h * h)
  const radius = Math.ceil(diagonal / 2 + TOPIC_CIRCLE_INNER_PADDING)
  return Math.max(MIN_TOPIC_RADIUS_CIRCLE_MAP, radius)
}
