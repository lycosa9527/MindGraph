/**
 * Tight crop around diagram nodes/edges for raster export (PNG/PDF/thumbnails).
 * fitForExport frames content in the viewport, but html-to-image still captures the full wrapper.
 */

export type DiagramExportContentBounds = {
  left: number
  top: number
  width: number
  height: number
}

const CONTENT_SELECTORS = [
  '.vue-flow__node',
  '.vue-flow__edge-path',
  '.vue-flow__connection-path',
  '.learning-sheet-overlay line',
  '.learning-sheet-overlay rect',
  '.learning-sheet-overlay text',
] as const

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

  for (const selector of CONTENT_SELECTORS) {
    container.querySelectorAll(selector).forEach((element) => {
      const rect = element.getBoundingClientRect()
      if (rect.width <= 0 && rect.height <= 0) return
      found = true
      minX = Math.min(minX, rect.left)
      minY = Math.min(minY, rect.top)
      maxX = Math.max(maxX, rect.right)
      maxY = Math.max(maxY, rect.bottom)
    })
  }

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
  return cropCanvasToContentBounds(
    canvas,
    container.clientWidth,
    container.clientHeight,
    bounds
  )
}
