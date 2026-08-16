/**
 * Text helpers for mind-map vector SVG export (real <text>/<tspan>, not images).
 *
 * Wrap column + line breaks come from ``mindMapTextWrap`` (shared with canvas hosts).
 */
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import {
  MIND_MAP_TEXT_LINE_HEIGHT,
  MIND_MAP_UNDERLINE_TEXT_LINE_HEIGHT,
  measureMindMapLabelWidthPx,
  measureMindMapNumberPrefixAdvancePx,
  resolveMindMapBranchBodyMaxWidthPx,
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

/**
 * Alphabetic baseline from the top of a CSS ``line-height`` box.
 * Half-leading plus a typical Latin/CJK em ascent — the old ``0.85 * fontSize``
 * from the line-box top sat a few px high in svg2pdf.
 */
const SVG_TEXT_EM_ASCENT = 0.8

export function mindMapSvgTextBaselineY(options: {
  boxY: number
  boxHeight: number
  blockHeight: number
  fontSize: number
  lineHeight: number
  paddingY: number
  borderWidth: number
}): number {
  const { boxY, boxHeight, blockHeight, fontSize, lineHeight, paddingY, borderWidth } =
    options
  const contentTop = boxY + borderWidth + paddingY
  const contentHeight = boxHeight - borderWidth * 2 - paddingY * 2
  const lineBoxTop =
    contentHeight > blockHeight
      ? contentTop + (contentHeight - blockHeight) / 2
      : contentTop
  const halfLeading = Math.max(0, (lineHeight - fontSize) / 2)
  return lineBoxTop + halfLeading + fontSize * SVG_TEXT_EM_ASCENT
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
  /** Side chrome; body wraps in the remaining column. */
  numberPrefix?: string
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
    numberPrefix = '',
  } = options

  const spans = parseMindMapExportText(rawText)
  const plain = spans.map((s) => s.text).join('')
  if (numberPrefix && role === 'branch') {
    return renderMindMapNumberedSvgText({
      x,
      y,
      width,
      height,
      plain,
      numberPrefix,
      fontSize,
      fontWeight,
      textColor,
      textAlign,
      paddingX,
      paddingY,
      borderWidth,
      underline,
    })
  }
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
  const startY = mindMapSvgTextBaselineY({
    boxY: y,
    boxHeight: height,
    blockHeight,
    fontSize,
    lineHeight,
    paddingY,
    borderWidth,
  })

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

function renderMindMapNumberedSvgText(options: {
  x: number
  y: number
  width: number
  height: number
  plain: string
  numberPrefix: string
  fontSize: number
  fontWeight: 'normal' | 'bold'
  textColor: string
  textAlign: 'left' | 'center' | 'right'
  paddingX: number
  paddingY: number
  borderWidth: number
  underline: boolean
}): string {
  const {
    x,
    y,
    width,
    height,
    plain,
    numberPrefix,
    fontSize,
    fontWeight,
    textColor,
    textAlign,
    paddingX,
    paddingY,
    borderWidth,
    underline,
  } = options
  const measureOpts = {
    fontWeight,
    fontFamily: MIND_MAP_GEOMETRY.fontFamily,
  }
  const prefixAdvance = measureMindMapNumberPrefixAdvancePx(numberPrefix, fontSize, measureOpts)
  const boxInner = width - paddingX * 2 - borderWidth * 2
  const hostBody = resolveMindMapBranchBodyMaxWidthPx(plain, numberPrefix, fontSize, measureOpts)
  const bodyCol = Math.max(8, Math.min(hostBody, Math.max(8, boxInner - prefixAdvance)))
  const lines =
    !plain.includes('\n') && measureMindMapLabelWidthPx(plain, fontSize, measureOpts) <= hostBody
      ? [plain || '']
      : wrapMindMapTextLines(plain, bodyCol, {
          fontSize,
          fontWeight,
          fontFamily: MIND_MAP_GEOMETRY.fontFamily,
        })
  const bodyWidth = Math.max(
    0,
    ...lines.map((line) => measureMindMapLabelWidthPx(line, fontSize, measureOpts))
  )
  const groupW = prefixAdvance + bodyWidth
  const innerLeft = x + paddingX + borderWidth
  const innerRight = x + width - paddingX - borderWidth
  let groupX = innerLeft
  if (textAlign === 'center') {
    groupX = x + (width - groupW) / 2
  } else if (textAlign === 'right') {
    groupX = innerRight - groupW
  }
  if (groupW < innerRight - innerLeft) {
    groupX = Math.max(innerLeft, Math.min(groupX, innerRight - groupW))
  } else {
    groupX = innerLeft
  }

  const lineHeightFactor = underline
    ? MIND_MAP_UNDERLINE_TEXT_LINE_HEIGHT
    : MIND_MAP_TEXT_LINE_HEIGHT
  const lineHeight = fontSize * lineHeightFactor
  const blockHeight = Math.max(1, lines.length) * lineHeight
  const bodyStartY = mindMapSvgTextBaselineY({
    boxY: y,
    boxHeight: height,
    blockHeight,
    fontSize,
    lineHeight,
    paddingY,
    borderWidth,
  })
  // Match canvas ``align-items: center``: prefix sits on the block midline.
  const prefixStartY = bodyStartY + (blockHeight - lineHeight) / 2
  const weightAttr = fontWeight === 'bold' ? ' font-weight="bold"' : ''
  const fontAttrs =
    `text-anchor="start" font-family="${escapeXml(MIND_MAP_VECTOR_FONT_FAMILY)}" ` +
    `font-size="${fontSize}"${weightAttr} fill="${escapeXml(textColor)}"`
  const prefixSvg =
    `<text x="${groupX}" y="${prefixStartY}" ${fontAttrs}>${escapeXml(numberPrefix)}</text>`
  const bodyX = groupX + prefixAdvance
  const tspans = lines.map((line, index) => {
    const dyAttr = index === 0 ? '' : ` dy="${lineHeight}"`
    return `<tspan x="${bodyX}"${dyAttr}>${escapeXml(line)}</tspan>`
  })
  const bodySvg = `<text x="${bodyX}" y="${bodyStartY}" ${fontAttrs}>${tspans.join('')}</text>`
  return `${prefixSvg}${bodySvg}`
}
