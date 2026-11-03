/**
 * html-to-image draws a CSS-sized SVG onto a canvas that is pixelRatio times larger.
 * Mobile browsers rasterize that SVG at 1× first, so clipboard and PNG saves are an
 * upscale of a phone-sized bitmap. Rewrite the SVG to the output pixel size (viewBox
 * stays in CSS pixels).
 *
 * The ratio follows the diagram. Small captures are raised until the long edge is
 * sharp. Large captures keep the requested ratio (usually 2×) until the canvas
 * budget, so a bigger diagram exports a bigger image.
 */
import { isTouchDeviceUserAgent } from '@/utils/isMobileClient'

/** Long edge we want when a 2× capture would still be a small bitmap. */
const SHARP_EXPORT_MIN_LONG_EDGE = 2400

/**
 * Desktop canvas budget. Chrome's hard edge is 16384; stay under it, and under
 * ~384MB of RGBA (96M pixels), so a large map can stay near 2×.
 */
export const DIAGRAM_RASTER_BUDGET_DESKTOP = {
  maxEdge: 15360,
  maxPixels: 96 * 1024 * 1024,
} as const

/** Phone and tablet canvases blank out above these limits. */
export const DIAGRAM_RASTER_BUDGET_MOBILE = {
  maxEdge: 4096,
  maxPixels: 16_777_216,
} as const

export type DiagramRasterBudget = {
  maxEdge: number
  maxPixels: number
}

const SVG_DATA_URL = /^data:image\/svg\+xml(?:;charset=utf-8)?,/i

/**
 * Touch browsers blank a canvas above the phone budget.
 * A narrow desktop window is still a desktop canvas, so window width is not used.
 */
export function diagramRasterExportBudget(userAgent?: string): DiagramRasterBudget {
  const ua = userAgent ?? (typeof navigator === 'undefined' ? '' : navigator.userAgent)
  if (!ua) return DIAGRAM_RASTER_BUDGET_DESKTOP
  return isTouchDeviceUserAgent(ua) ? DIAGRAM_RASTER_BUDGET_MOBILE : DIAGRAM_RASTER_BUDGET_DESKTOP
}

/**
 * Largest zoom that keeps a 1× capture of this diagram inside the bitmap budget.
 * The pixel ratio then raises that capture, usually to 2×, while the same budget
 * still has room.
 */
export function resolveDiagramExportZoom(
  contentWidth: number,
  contentHeight: number,
  pad: number,
  budget: DiagramRasterBudget = DIAGRAM_RASTER_BUDGET_DESKTOP
): number {
  const width = Math.max(1, contentWidth)
  const height = Math.max(1, contentHeight)
  const padPx = Math.max(0, pad) * 2
  const edgeRoom = Math.max(0, budget.maxEdge - padPx)
  const edgeZoom = Math.min(edgeRoom / width, edgeRoom / height)
  const a = width * height
  const b = padPx * (width + height)
  const c = padPx * padPx - budget.maxPixels
  const discriminant = b * b - 4 * a * c
  const areaZoom = discriminant > 0 ? (-b + Math.sqrt(discriminant)) / (2 * a) : edgeZoom
  return Math.min(1, edgeZoom, areaZoom)
}

export function resolveDiagramRasterPixelRatio(
  cssWidth: number,
  cssHeight: number,
  requested = 2,
  budget: DiagramRasterBudget = DIAGRAM_RASTER_BUDGET_DESKTOP
): number {
  const width = Math.max(1, cssWidth)
  const height = Math.max(1, cssHeight)
  const longEdge = Math.max(width, height)
  const safeRequested = Math.max(requested, 1)
  const maxRatio = Math.min(
    budget.maxEdge / longEdge,
    Math.sqrt(budget.maxPixels / (width * height))
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
export function scaleExportSvgDataUrl(
  dataUrl: string,
  requestedPixelRatio = 2,
  budget: DiagramRasterBudget = DIAGRAM_RASTER_BUDGET_DESKTOP
): ScaledExportSvg {
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
  const pixelRatio = resolveDiagramRasterPixelRatio(
    cssWidth,
    cssHeight,
    requestedPixelRatio,
    budget
  )
  const fitted = fitRasterSize(cssWidth, cssHeight, pixelRatio, budget)
  if (!svg.getAttribute('viewBox')) {
    svg.setAttribute('viewBox', `0 0 ${cssWidth} ${cssHeight}`)
  }
  svg.setAttribute('width', String(fitted.width))
  svg.setAttribute('height', String(fitted.height))
  const xml = new XMLSerializer().serializeToString(svg)
  return {
    dataUrl: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(xml)}`,
    width: fitted.width,
    height: fitted.height,
    pixelRatio: fitted.pixelRatio,
  }
}

/** Rounding can land one pixel past the budget. Floor back inside it. */
function fitRasterSize(
  cssWidth: number,
  cssHeight: number,
  pixelRatio: number,
  budget: DiagramRasterBudget
): { width: number; height: number; pixelRatio: number } {
  const width = Math.max(1, Math.round(cssWidth * pixelRatio))
  const height = Math.max(1, Math.round(cssHeight * pixelRatio))
  if (width <= budget.maxEdge && height <= budget.maxEdge && width * height <= budget.maxPixels) {
    return { width, height, pixelRatio }
  }
  const fittedRatio = Math.min(
    pixelRatio,
    budget.maxEdge / cssWidth,
    budget.maxEdge / cssHeight,
    Math.sqrt(budget.maxPixels / (cssWidth * cssHeight))
  )
  return {
    width: Math.max(1, Math.floor(cssWidth * fittedRatio)),
    height: Math.max(1, Math.floor(cssHeight * fittedRatio)),
    pixelRatio: fittedRatio,
  }
}
