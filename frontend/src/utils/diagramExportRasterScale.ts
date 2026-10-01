/**
 * html-to-image draws a CSS-sized SVG onto a canvas that is pixelRatio times larger.
 * Mobile browsers rasterize that SVG at 1× first, so clipboard and PNG saves are an
 * upscale of a phone-sized bitmap. Rewrite the SVG to the output pixel size (viewBox
 * stays in CSS pixels) and only raise the ratio when the on-screen capture is small.
 */

/** Long edge we want for a sharp phone export. Desktop 2× captures already clear this. */
const SHARP_EXPORT_MIN_LONG_EDGE = 2400

/** Stay under common mobile canvas limits (edge and area). */
const SHARP_EXPORT_MAX_EDGE = 4096
const SHARP_EXPORT_MAX_PIXELS = 16_777_216

const SVG_DATA_URL = /^data:image\/svg\+xml(?:;charset=utf-8)?,/i

export function resolveDiagramRasterPixelRatio(
  cssWidth: number,
  cssHeight: number,
  requested = 2
): number {
  const width = Math.max(1, cssWidth)
  const height = Math.max(1, cssHeight)
  const longEdge = Math.max(width, height)
  const safeRequested = Math.max(requested, 1)
  const maxRatio = Math.min(
    SHARP_EXPORT_MAX_EDGE / longEdge,
    Math.sqrt(SHARP_EXPORT_MAX_PIXELS / (width * height))
  )
  if (!(safeRequested > 1)) return Math.min(1, maxRatio)
  const boosted =
    longEdge * safeRequested >= SHARP_EXPORT_MIN_LONG_EDGE
      ? safeRequested
      : SHARP_EXPORT_MIN_LONG_EDGE / longEdge
  return Math.min(boosted, maxRatio)
}

export function svgMarkupFromDataUrl(dataUrl: string): string {
  const match = SVG_DATA_URL.exec(dataUrl)
  if (!match) {
    throw new Error('Export SVG data URL is invalid')
  }
  return decodeURIComponent(dataUrl.slice(match[0].length))
}

function readSvgLength(value: string | null): number {
  if (!value) return Number.NaN
  const parsed = Number.parseFloat(value)
  return Number.isFinite(parsed) ? parsed : Number.NaN
}

export type ScaledExportSvg = {
  dataUrl: string
  width: number
  height: number
  pixelRatio: number
}

/** Paint the export SVG at output pixels so the canvas is not a stretched 1× bitmap. */
export function scaleExportSvgDataUrl(dataUrl: string, requestedPixelRatio = 2): ScaledExportSvg {
  const markup = svgMarkupFromDataUrl(dataUrl)
  const doc = new DOMParser().parseFromString(markup, 'image/svg+xml')
  const svg = doc.documentElement
  if (svg.tagName.toLowerCase() === 'parsererror') {
    throw new Error('Export SVG markup is invalid')
  }
  const cssWidth = readSvgLength(svg.getAttribute('width'))
  const cssHeight = readSvgLength(svg.getAttribute('height'))
  if (!(cssWidth > 0) || !(cssHeight > 0)) {
    throw new Error('Export SVG size is missing')
  }
  const pixelRatio = resolveDiagramRasterPixelRatio(cssWidth, cssHeight, requestedPixelRatio)
  const width = Math.max(1, Math.round(cssWidth * pixelRatio))
  const height = Math.max(1, Math.round(cssHeight * pixelRatio))
  if (!svg.getAttribute('viewBox')) {
    svg.setAttribute('viewBox', `0 0 ${cssWidth} ${cssHeight}`)
  }
  svg.setAttribute('width', String(width))
  svg.setAttribute('height', String(height))
  const xml = new XMLSerializer().serializeToString(svg)
  return {
    dataUrl: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(xml)}`,
    width,
    height,
    pixelRatio,
  }
}
