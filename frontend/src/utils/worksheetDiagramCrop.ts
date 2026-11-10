/**
 * Worksheet diagram crop — fractions of the source image removed from each edge.
 * 0 = no crop. Opposite edges stay within a minimum visible window.
 */

export interface WorksheetDiagramCrop {
  top: number
  right: number
  bottom: number
  left: number
}

export type WorksheetDiagramCropEdge = 'top' | 'right' | 'bottom' | 'left'

export const ZERO_WORKSHEET_DIAGRAM_CROP: WorksheetDiagramCrop = {
  top: 0,
  right: 0,
  bottom: 0,
  left: 0,
}

/** One edge cannot hide more than this fraction of the image. */
const WORKSHEET_DIAGRAM_CROP_MAX = 0.75
/** Opposite edges together must leave at least this fraction visible. */
const WORKSHEET_DIAGRAM_CROP_MIN_VISIBLE = 0.2

const CROP_ACTIVE_EPSILON = 0.001

export interface WorksheetDiagramViewBox {
  minX: number
  minY: number
  width: number
  height: number
}

function finiteOrZero(value: number): number {
  return Number.isFinite(value) ? value : 0
}

function clampWorksheetDiagramCropEdge(value: number): number {
  return Math.max(0, Math.min(WORKSHEET_DIAGRAM_CROP_MAX, finiteOrZero(value)))
}

/** Limit the edge being dragged so the opposite edge stays put. */
export function clampCropEdgeAgainstOpposite(moving: number, opposite: number): number {
  const maxMoving = Math.min(
    WORKSHEET_DIAGRAM_CROP_MAX,
    1 - WORKSHEET_DIAGRAM_CROP_MIN_VISIBLE - Math.max(0, finiteOrZero(opposite))
  )
  return Math.max(0, Math.min(maxMoving, finiteOrZero(moving)))
}

function scalePair(a: number, b: number, maxSum: number): { a: number; b: number } {
  const sum = a + b
  if (sum <= maxSum || sum <= 0) return { a, b }
  const factor = maxSum / sum
  return { a: a * factor, b: b * factor }
}

export function normalizeWorksheetDiagramCrop(
  crop: WorksheetDiagramCrop | undefined
): WorksheetDiagramCrop {
  if (!crop) return { ...ZERO_WORKSHEET_DIAGRAM_CROP }
  const maxSum = 1 - WORKSHEET_DIAGRAM_CROP_MIN_VISIBLE
  const vertical = scalePair(
    clampWorksheetDiagramCropEdge(crop.top),
    clampWorksheetDiagramCropEdge(crop.bottom),
    maxSum
  )
  const horizontal = scalePair(
    clampWorksheetDiagramCropEdge(crop.left),
    clampWorksheetDiagramCropEdge(crop.right),
    maxSum
  )
  return {
    top: vertical.a,
    bottom: vertical.b,
    left: horizontal.a,
    right: horizontal.b,
  }
}

export function worksheetDiagramCropFractions(crop: WorksheetDiagramCrop | undefined): {
  cw: number
  ch: number
} {
  const normalized = normalizeWorksheetDiagramCrop(crop)
  return {
    cw: 1 - normalized.left - normalized.right,
    ch: 1 - normalized.top - normalized.bottom,
  }
}

export function worksheetDiagramCropIsActive(crop: WorksheetDiagramCrop | undefined): boolean {
  const normalized = normalizeWorksheetDiagramCrop(crop)
  return (
    normalized.top > CROP_ACTIVE_EPSILON ||
    normalized.right > CROP_ACTIVE_EPSILON ||
    normalized.bottom > CROP_ACTIVE_EPSILON ||
    normalized.left > CROP_ACTIVE_EPSILON
  )
}

export function worksheetDiagramHasCustomPlacement(
  offsetX: number,
  offsetY: number,
  scale: number,
  crop: WorksheetDiagramCrop | undefined
): boolean {
  return offsetX !== 0 || offsetY !== 0 || scale !== 1 || worksheetDiagramCropIsActive(crop)
}

/**
 * Drag one crop bar. Positive delta grows top/left crops and shrinks bottom/right crops,
 * matching Word: pull an edge inward to hide that side.
 */
export function cropEdgeFromDelta(
  edge: WorksheetDiagramCropEdge,
  start: WorksheetDiagramCrop,
  deltaPx: number,
  spanPx: number
): WorksheetDiagramCrop {
  const base = normalizeWorksheetDiagramCrop(start)
  if (!(spanPx > 0) || !Number.isFinite(deltaPx)) return base
  const signed = edge === 'bottom' || edge === 'right' ? -deltaPx : deltaPx
  const next = signed / spanPx
  if (edge === 'top') {
    return { ...base, top: clampCropEdgeAgainstOpposite(base.top + next, base.bottom) }
  }
  if (edge === 'bottom') {
    return { ...base, bottom: clampCropEdgeAgainstOpposite(base.bottom + next, base.top) }
  }
  if (edge === 'left') {
    return { ...base, left: clampCropEdgeAgainstOpposite(base.left + next, base.right) }
  }
  return { ...base, right: clampCropEdgeAgainstOpposite(base.right + next, base.left) }
}

/** Arrow-key sign for cropEdgeFromDelta. Inward grows the crop; 0 ignores the key. */
export function worksheetDiagramCropKeyDelta(edge: WorksheetDiagramCropEdge, key: string): number {
  const inward =
    (edge === 'top' && key === 'ArrowDown') ||
    (edge === 'bottom' && key === 'ArrowUp') ||
    (edge === 'left' && key === 'ArrowRight') ||
    (edge === 'right' && key === 'ArrowLeft')
  if (inward) return edge === 'top' || edge === 'left' ? 1 : -1
  const outward =
    (edge === 'top' && key === 'ArrowUp') ||
    (edge === 'bottom' && key === 'ArrowDown') ||
    (edge === 'left' && key === 'ArrowLeft') ||
    (edge === 'right' && key === 'ArrowRight')
  if (outward) return edge === 'top' || edge === 'left' ? -1 : 1
  return 0
}

/** Normalized offset that keeps one edge of the frame fixed while the opposite edge moves. */
export function offsetForAnchoredEdge(args: {
  bodySize: number
  visibleSize: number
  fixedEdge: number
  anchor: 'start' | 'end'
}): number {
  const bodySize = finiteOrZero(args.bodySize)
  const visibleSize = Math.max(0, finiteOrZero(args.visibleSize))
  const free = Math.max(0, bodySize - visibleSize)
  if (free <= 0 || bodySize <= 0) return 0
  const origin = args.anchor === 'start' ? args.fixedEdge : args.fixedEdge - visibleSize
  const center = origin + visibleSize / 2
  const offset = (center - bodySize / 2) / (free / 2)
  return Math.max(-1, Math.min(1, offset))
}

export function worksheetDiagramFrameOrigin(
  bodyWidth: number,
  bodyHeight: number,
  frameWidth: number,
  frameHeight: number,
  offsetX: number,
  offsetY: number
): { left: number; top: number; right: number; bottom: number } {
  const freeW = Math.max(0, bodyWidth - frameWidth)
  const freeH = Math.max(0, bodyHeight - frameHeight)
  const ox = Math.max(-1, Math.min(1, finiteOrZero(offsetX)))
  const oy = Math.max(-1, Math.min(1, finiteOrZero(offsetY)))
  const centerX = bodyWidth / 2 + (ox * freeW) / 2
  const centerY = bodyHeight / 2 + (oy * freeH) / 2
  return {
    left: centerX - frameWidth / 2,
    top: centerY - frameHeight / 2,
    right: centerX + frameWidth / 2,
    bottom: centerY + frameHeight / 2,
  }
}

function formatSvgNumber(value: number): string {
  if (!Number.isFinite(value)) return '0'
  return String(Math.round(value * 1000) / 1000)
}

/** Rewrite attributes on the opening svg tag only, so child shapes keep their own sizes. */
function rewriteSvgRoot(svg: string, attrs: Record<string, string>): string {
  const match = /<svg\b[^>]*>/.exec(svg)
  if (!match) return svg
  let tag = match[0]
  for (const [name, value] of Object.entries(attrs)) {
    const encoded = `${name}="${value}"`
    const pattern = new RegExp(`\\s${name}="[^"]*"`)
    if (pattern.test(tag)) {
      tag = tag.replace(pattern, ` ${encoded}`)
    } else {
      tag = tag.replace('<svg', `<svg ${encoded}`)
    }
  }
  return svg.slice(0, match.index) + tag + svg.slice(match.index + match[0].length)
}

/** Shrink the root SVG viewBox so vector PDF export draws the cropped window. */
export function applyWorksheetDiagramCropToSvg(
  svg: string,
  viewBox: WorksheetDiagramViewBox,
  crop: WorksheetDiagramCrop | undefined
): { svg: string; viewBox: WorksheetDiagramViewBox } {
  if (!worksheetDiagramCropIsActive(crop)) {
    return { svg, viewBox }
  }
  const normalized = normalizeWorksheetDiagramCrop(crop)
  const { cw, ch } = worksheetDiagramCropFractions(normalized)
  const next: WorksheetDiagramViewBox = {
    minX: viewBox.minX + viewBox.width * normalized.left,
    minY: viewBox.minY + viewBox.height * normalized.top,
    width: Math.max(1, viewBox.width * cw),
    height: Math.max(1, viewBox.height * ch),
  }
  const croppedSvg = rewriteSvgRoot(svg, {
    width: formatSvgNumber(next.width),
    height: formatSvgNumber(next.height),
    viewBox: `${formatSvgNumber(next.minX)} ${formatSvgNumber(next.minY)} ${formatSvgNumber(next.width)} ${formatSvgNumber(next.height)}`,
    overflow: 'hidden',
  })
  return { svg: croppedSvg, viewBox: next }
}
