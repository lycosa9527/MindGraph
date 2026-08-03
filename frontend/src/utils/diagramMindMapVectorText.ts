/**
 * Text helpers for mind-map vector SVG export (real <text>/<tspan>, not images).
 *
 * Wrap column + line breaks come from ``mindMapTextWrap`` (shared with canvas hosts).
 */
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import {
  MIND_MAP_TEXT_LINE_HEIGHT,
  MIND_MAP_UNDERLINE_TEXT_LINE_HEIGHT,
  wrapMindMapExportLabelLines,
  wrapMindMapTextLines,
  type MindMapTextWrapRole,
} from '@/utils/mindMapTextWrap'
import { estimateTextWidthFallbackPx } from '@/stores/specLoader/textMeasurementFallback'

/** Noto first so svg2pdf resolves a registered CJK-capable face before Inter. */
export const MIND_MAP_VECTOR_FONT_FAMILY = 'Noto Sans SC, Inter, sans-serif'

/** jsPDF / svg2pdf registered family names (first match wins in SVG). */
export const MIND_MAP_VECTOR_PDF_FONT_NOTO = 'Noto Sans SC'
export const MIND_MAP_VECTOR_PDF_FONT_INTER = 'Inter'

/** @deprecated Prefer MIND_MAP_TEXT_LINE_HEIGHT from mindMapTextWrap. */
export const MIND_MAP_VECTOR_LINE_HEIGHT = MIND_MAP_TEXT_LINE_HEIGHT

export type MindMapVectorTextSpan = {
  text: string
  bold: boolean
}

export type MindMapVectorWrapOptions = {
  fontWeight?: 'normal' | 'bold'
  fontFamily?: string
}

export function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

/**
 * Strip Markdown / KaTeX to plain text; keep simple **bold** / __bold__ as spans.
 */
export function parseMindMapExportText(raw: string): MindMapVectorTextSpan[] {
  const withoutCode = raw.replace(/`([^`]+)`/g, '$1')
  const withoutMath = withoutCode
    .replace(/\$\$[\s\S]*?\$\$/g, ' ')
    .replace(/\$[^$\n]+\$/g, ' ')
    .replace(/\\\[[\s\S]*?\\\]/g, ' ')
    .replace(/\\\([\s\S]*?\\\)/g, ' ')
  const withoutMdNoise = withoutMath
    .replace(/!\[[^\]]*]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)]\([^)]*\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/\r\n/g, '\n')

  const spans: MindMapVectorTextSpan[] = []
  const boldRe = /(\*\*|__)(.+?)\1/g
  let last = 0
  let match: RegExpExecArray | null
  while ((match = boldRe.exec(withoutMdNoise)) !== null) {
    if (match.index > last) {
      pushPlain(spans, withoutMdNoise.slice(last, match.index))
    }
    pushPlain(spans, match[2], true)
    last = match.index + match[0].length
  }
  if (last < withoutMdNoise.length) {
    pushPlain(spans, withoutMdNoise.slice(last))
  }
  if (spans.length === 0) {
    return [{ text: '', bold: false }]
  }
  return spans
}

function pushPlain(spans: MindMapVectorTextSpan[], text: string, bold = false): void {
  const normalized = text.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n')
  if (!normalized) return
  const prev = spans[spans.length - 1]
  if (prev && prev.bold === bold) {
    prev.text += normalized
    return
  }
  spans.push({ text: normalized, bold })
}

export function mindMapExportPlainText(raw: string): string {
  return parseMindMapExportText(raw)
    .map((span) => span.text)
    .join('')
    .replace(/\s+/g, ' ')
    .trim()
}

export function estimateTextWidth(
  text: string,
  fontSize: number,
  options?: { isTopic?: boolean }
): number {
  return estimateTextWidthFallbackPx(text, fontSize, options)
}

/** @deprecated Use wrapMindMapTextLines from mindMapTextWrap. */
export function wrapMindMapExportLines(
  plain: string,
  maxWidth: number,
  fontSize: number,
  options: MindMapVectorWrapOptions = {}
): string[] {
  return wrapMindMapTextLines(plain, maxWidth, {
    fontSize,
    fontWeight: options.fontWeight,
    fontFamily: options.fontFamily ?? MIND_MAP_GEOMETRY.fontFamily,
  })
}

export function renderMindMapSvgText(options: {
  x: number
  y: number
  width: number
  height: number
  rawText: string
  fontSize: number
  fontWeight?: 'normal' | 'bold'
  textColor: string
  textAlign?: 'left' | 'center' | 'right'
  paddingX: number
  paddingY: number
  borderWidth?: number
  role?: MindMapTextWrapRole
  /** Underline shapes use line-height 1.35 on canvas. */
  underline?: boolean
}): string {
  const {
    x,
    y,
    width,
    height,
    rawText,
    fontSize,
    fontWeight = 'normal',
    textColor,
    textAlign = 'center',
    paddingX,
    paddingY,
    borderWidth = 0,
    role = 'branch',
    underline = false,
  } = options

  const spans = parseMindMapExportText(rawText)
  const plain = spans.map((s) => s.text).join('')
  const lines = wrapMindMapExportLabelLines({
    role,
    text: plain,
    fontSize,
    fontWeight,
    fontFamily: MIND_MAP_GEOMETRY.fontFamily,
    boxWidth: width,
    paddingX,
    borderWidth,
  })

  const lineHeightFactor = underline
    ? MIND_MAP_UNDERLINE_TEXT_LINE_HEIGHT
    : MIND_MAP_TEXT_LINE_HEIGHT
  const lineHeight = fontSize * lineHeightFactor
  const blockHeight = lines.length * lineHeight
  const startY = y + Math.max(paddingY, (height - blockHeight) / 2) + fontSize * 0.85

  let anchor = 'middle'
  let textX = x + width / 2
  if (textAlign === 'left') {
    anchor = 'start'
    textX = x + paddingX
  } else if (textAlign === 'right') {
    anchor = 'end'
    textX = x + width - paddingX
  }

  const weightAttr = fontWeight === 'bold' ? ' font-weight="bold"' : ''
  const parts: string[] = []
  lines.forEach((line, index) => {
    const dy = index === 0 ? 0 : lineHeight
    const dyAttr = index === 0 ? '' : ` dy="${dy}"`
    parts.push(`<tspan x="${textX}"${dyAttr}>${escapeXml(line)}</tspan>`)
  })

  return (
    `<text x="${textX}" y="${startY}" text-anchor="${anchor}" ` +
    `font-family="${escapeXml(MIND_MAP_VECTOR_FONT_FAMILY)}" font-size="${fontSize}"` +
    `${weightAttr} fill="${escapeXml(textColor)}">${parts.join('')}</text>`
  )
}
