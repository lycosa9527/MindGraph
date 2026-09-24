/**
 * Frame and crop raster export (PNG/PDF/thumbnails) around painted diagram ink.
 * Vue Flow fitView only sees node boxes. Braces, captions, and curved edges
 * extend past those boxes, so a node-only frame clips them once zoom makes
 * that overflow larger than the viewport padding.
 */

export type DiagramExportContentBounds = {
  left: number
  top: number
  width: number
  height: number
}

export type DiagramExportFlowRect = {
  x: number
  y: number
  width: number
  height: number
}

export type DiagramExportFlowNode = {
  hidden?: boolean
  position?: { x?: number; y?: number }
  computedPosition?: { x?: number; y?: number }
  dimensions?: { width?: number; height?: number }
  measured?: { width?: number; height?: number }
  width?: number
  height?: number
}

/** Stroke and arrow markers are outside SVG getBBox. */
export const DIAGRAM_EXPORT_FLOW_PAD = 12

const INK_SELECTOR = [
  '.vue-flow__node',
  '.vue-flow__edge-path',
  '.vue-flow__edge-text',
  '.vue-flow__connection-path',
  '.brace-overlay path',
  '.brace-overlay line',
  '.brace-overlay polygon',
  '.brace-overlay text',
  '.tree-map-overlay path',
  '.tree-map-overlay line',
  '.tree-map-overlay polygon',
  '.tree-map-overlay text',
  '.bridge-overlay path',
  '.bridge-overlay line',
  '.bridge-overlay polygon',
  '.bridge-overlay text',
  '.mm-summary-overlay path',
  '.mm-summary-overlay line',
  '.mm-summary-overlay polygon',
  '.mm-summary-overlay text',
  '.mm-summary-overlay rect',
  '.learning-sheet-overlay path',
  '.learning-sheet-overlay line',
  '.learning-sheet-overlay polygon',
  '.learning-sheet-overlay text',
  '.learning-sheet-overlay rect',
].join(', ')

function forEachExportInkElement(container: HTMLElement, visit: (element: Element) => void): void {
  container.querySelectorAll(INK_SELECTOR).forEach((element) => {
    visit(element)
  })
}

export function nodeToExportFlowRect(node: DiagramExportFlowNode): DiagramExportFlowRect | null {
  if (node.hidden) return null
  const x = node.computedPosition?.x ?? node.position?.x
  const y = node.computedPosition?.y ?? node.position?.y
  if (x === undefined || y === undefined || !Number.isFinite(x) || !Number.isFinite(y)) {
    return null
  }
  const width = node.dimensions?.width ?? node.measured?.width ?? node.width ?? 0
  const height = node.dimensions?.height ?? node.measured?.height ?? node.height ?? 0
  if (!(width > 0) || !(height > 0)) return null
  return { x, y, width, height }
}

export function unionFlowRects(
  rects: readonly DiagramExportFlowRect[],
  pad = 0
): DiagramExportFlowRect | null {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const rect of rects) {
    if (!(rect.width > 0) && !(rect.height > 0)) continue
    minX = Math.min(minX, rect.x)
    minY = Math.min(minY, rect.y)
    maxX = Math.max(maxX, rect.x + Math.max(0, rect.width))
    maxY = Math.max(maxY, rect.y + Math.max(0, rect.height))
  }
  if (!Number.isFinite(minX) || !Number.isFinite(minY)) return null
  return {
    x: minX - pad,
    y: minY - pad,
    width: Math.max(1, maxX - minX + pad * 2),
    height: Math.max(1, maxY - minY + pad * 2),
  }
}

function readSvgLocalBounds(element: Element): DiagramExportFlowRect | null {
  if (!(element instanceof SVGElement)) return null
  const graphics = element as SVGGraphicsElement
  if (typeof graphics.getBBox !== 'function') return null
  let box: DOMRect
  try {
    box = graphics.getBBox()
  } catch (error) {
    if (error instanceof DOMException) return null
    throw error
  }
  if (box.width <= 0 && box.height <= 0) return null
  return { x: box.x, y: box.y, width: box.width, height: box.height }
}

/**
 * Flow-space bounds of nodes plus overlay/edge geometry.
 * SVG getBBox ignores the viewport transform, so path data stays in flow units.
 */
export function measureDiagramExportFlowBounds(
  container: HTMLElement,
  nodes: readonly DiagramExportFlowNode[],
  pad = DIAGRAM_EXPORT_FLOW_PAD
): DiagramExportFlowRect | null {
  const rects: DiagramExportFlowRect[] = []
  for (const node of nodes) {
    const rect = nodeToExportFlowRect(node)
    if (rect) rects.push(rect)
  }
  forEachExportInkElement(container, (element) => {
    const rect = readSvgLocalBounds(element)
    if (rect) rects.push(rect)
  })
  return unionFlowRects(rects, pad)
}

export function measureDiagramExportContentBounds(
  container: HTMLElement,
  paddingPx = 24
): DiagramExportContentBounds | null {
  const containerRect = container.getBoundingClientRect()
  if (containerRect.width <= 0 || containerRect.height <= 0) {
    return null
  }

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  let found = false

  forEachExportInkElement(container, (element) => {
    const rect = element.getBoundingClientRect()
    if (rect.width <= 0 && rect.height <= 0) return
    found = true
    minX = Math.min(minX, rect.left)
    minY = Math.min(minY, rect.top)
    maxX = Math.max(maxX, rect.right)
    maxY = Math.max(maxY, rect.bottom)
  })

  if (!found || !Number.isFinite(minX) || !Number.isFinite(minY)) {
    return null
  }

  const left = Math.max(0, minX - containerRect.left - paddingPx)
  const top = Math.max(0, minY - containerRect.top - paddingPx)
  const right = Math.min(containerRect.width, maxX - containerRect.left + paddingPx)
  const bottom = Math.min(containerRect.height, maxY - containerRect.top + paddingPx)

  return {
    left,
    top,
    width: Math.max(1, right - left),
    height: Math.max(1, bottom - top),
  }
}

export function computeDiagramExportCropRegion(
  sourceWidth: number,
  sourceHeight: number,
  containerWidth: number,
  containerHeight: number,
  bounds: DiagramExportContentBounds
): { sx: number; sy: number; sw: number; sh: number } {
  const scaleX = sourceWidth / Math.max(1, containerWidth)
  const scaleY = sourceHeight / Math.max(1, containerHeight)
  const sx = Math.max(0, Math.round(bounds.left * scaleX))
  const sy = Math.max(0, Math.round(bounds.top * scaleY))
  const sw = Math.min(sourceWidth - sx, Math.max(1, Math.round(bounds.width * scaleX)))
  const sh = Math.min(sourceHeight - sy, Math.max(1, Math.round(bounds.height * scaleY)))
  return { sx, sy, sw, sh }
}

export function cropCanvasToContentBounds(
  source: HTMLCanvasElement,
  containerWidth: number,
  containerHeight: number,
  bounds: DiagramExportContentBounds
): HTMLCanvasElement {
  const { sx, sy, sw, sh } = computeDiagramExportCropRegion(
    source.width,
    source.height,
    containerWidth,
    containerHeight,
    bounds
  )

  if (sx === 0 && sy === 0 && sw === source.width && sh === source.height) {
    return source
  }

  const cropped = document.createElement('canvas')
  cropped.width = sw
  cropped.height = sh
  const ctx = cropped.getContext('2d')
  if (!ctx) {
    throw new Error('Canvas 2D context unavailable for export crop')
  }
  ctx.drawImage(source, sx, sy, sw, sh, 0, 0, sw, sh)
  return cropped
}

export function cropExportedDiagramCanvas(
  container: HTMLElement,
  canvas: HTMLCanvasElement,
  paddingPx = 24
): HTMLCanvasElement {
  const bounds = measureDiagramExportContentBounds(container, paddingPx)
  if (!bounds) {
    return canvas
  }
  return cropCanvasToContentBounds(canvas, container.clientWidth, container.clientHeight, bounds)
}
