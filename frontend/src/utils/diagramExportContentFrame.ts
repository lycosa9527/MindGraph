/**
 * Raster export frame for diagrams that are larger than the window.
 * Fit-to-window paints text at the fitted zoom; the PNG is that shrunken bitmap.
 * Size the capture to the diagram instead, capped so the canvas stays drawable.
 */
import { nextTick } from 'vue'

import { ZOOM } from '@/config/uiConfig'
import {
  type DiagramExportFlowNode,
  type DiagramExportFlowRect,
  measureDiagramExportFlowBounds,
} from '@/utils/diagramExportContentBounds'
import { waitForNextPaint } from '@/utils/diagramHtmlToImage'

/** Room for relationship labels and pill shadows outside node boxes. */
export const DIAGRAM_EXPORT_CONTENT_FRAME_PAD = 48

/** CSS edge before html-to-image applies its pixel ratio. */
const MAX_CAPTURE_EDGE = 4096

const MIN_CAPTURE_ZOOM = 0.02

const FRAME_STYLE_PROPS = ['width', 'height', 'maxWidth', 'maxHeight', 'flex'] as const

export type DiagramExportContentFrame = {
  zoom: number
  width: number
  height: number
  x: number
  y: number
}

export type DiagramExportViewport = {
  x: number
  y: number
  zoom: number
}

export function resolveDiagramExportContentFrame(
  bounds: DiagramExportFlowRect,
  pad = DIAGRAM_EXPORT_CONTENT_FRAME_PAD
): DiagramExportContentFrame {
  const contentW = Math.max(1, bounds.width)
  const contentH = Math.max(1, bounds.height)
  const innerEdge = Math.max(1, MAX_CAPTURE_EDGE - pad * 2)
  const zoom = Math.max(MIN_CAPTURE_ZOOM, Math.min(1, innerEdge / contentW, innerEdge / contentH))
  return {
    zoom,
    width: Math.ceil(contentW * zoom + pad * 2),
    height: Math.ceil(contentH * zoom + pad * 2),
    x: pad - bounds.x * zoom,
    y: pad - bounds.y * zoom,
  }
}

function readFrameStyles(
  container: HTMLElement
): Record<(typeof FRAME_STYLE_PROPS)[number], string> {
  return {
    width: container.style.width,
    height: container.style.height,
    maxWidth: container.style.maxWidth,
    maxHeight: container.style.maxHeight,
    flex: container.style.flex,
  }
}

function writeFrameStyles(
  container: HTMLElement,
  styles: Record<(typeof FRAME_STYLE_PROPS)[number], string>
): void {
  for (const prop of FRAME_STYLE_PROPS) {
    container.style[prop] = styles[prop]
  }
}

export async function withDiagramExportContentFrame<T>(
  options: {
    container: HTMLElement
    nodes: readonly DiagramExportFlowNode[]
    setViewport: (
      viewport: DiagramExportViewport,
      opts?: { duration?: number }
    ) => void | Promise<unknown>
    setMinZoom?: (zoom: number) => void
    savedViewport: DiagramExportViewport
  },
  run: () => Promise<T>
): Promise<T> {
  const bounds = measureDiagramExportFlowBounds(options.container, options.nodes)
  if (!bounds) {
    return run()
  }

  const frame = resolveDiagramExportContentFrame(bounds)
  const previousStyles = readFrameStyles(options.container)
  const previousMinZoom = ZOOM.MIN
  options.setMinZoom?.(Math.min(previousMinZoom, frame.zoom))
  options.container.style.width = `${frame.width}px`
  options.container.style.height = `${frame.height}px`
  options.container.style.maxWidth = 'none'
  options.container.style.maxHeight = 'none'
  options.container.style.flex = 'none'

  let restored = false
  async function restore(): Promise<void> {
    if (restored) return
    restored = true
    try {
      await options.setViewport(options.savedViewport, { duration: 0 })
    } finally {
      writeFrameStyles(options.container, previousStyles)
      options.setMinZoom?.(previousMinZoom)
    }
  }

  try {
    await nextTick()
    await waitForNextPaint()
    await options.setViewport({ x: frame.x, y: frame.y, zoom: frame.zoom }, { duration: 0 })
    await nextTick()
    await waitForNextPaint()
    return await run()
  } finally {
    await restore()
  }
}
