/**
 * Frame nodes in the canvas that is still visible beside a right-hand overlay.
 * fitView centers on the full canvas, which hides the subject under that overlay.
 */

export interface OpenCanvasFrameNode {
  id?: string
  position?: { x?: number; y?: number }
  computedPosition?: { x?: number; y?: number }
  dimensions?: { width?: number; height?: number }
  measured?: { width?: number; height?: number }
  width?: number
  height?: number
}

export interface OpenCanvasFrameInput {
  nodes: readonly OpenCanvasFrameNode[]
  nodeIds: readonly string[]
  canvasWidth: number
  canvasHeight: number
  occludeRightPx: number
  minZoom: number
  maxZoom: number
  viewport: { x: number; y: number; zoom: number }
}

const FRAME_MARGIN_PX = 36

export function frameNodesInOpenCanvas(
  input: OpenCanvasFrameInput
): { x: number; y: number; zoom: number } | null {
  if (input.occludeRightPx <= 0) return null
  const visibleWidth = input.canvasWidth - input.occludeRightPx
  if (visibleWidth < 80 || input.canvasHeight < 80) return null
  const bounds = boundsOfNodes(input.nodes, input.nodeIds)
  if (!bounds) {
    return {
      x: input.viewport.x - input.occludeRightPx / 2,
      y: input.viewport.y,
      zoom: input.viewport.zoom,
    }
  }
  const fitZoom = Math.min(
    (visibleWidth - FRAME_MARGIN_PX * 2) / Math.max(bounds.width, 1),
    (input.canvasHeight - FRAME_MARGIN_PX * 2) / Math.max(bounds.height, 1)
  )
  const zoom = Math.min(input.maxZoom, Math.max(input.minZoom, fitZoom))
  return {
    zoom,
    x: visibleWidth / 2 - (bounds.x + bounds.width / 2) * zoom,
    y: input.canvasHeight / 2 - (bounds.y + bounds.height / 2) * zoom,
  }
}

function boundsOfNodes(
  nodes: readonly OpenCanvasFrameNode[],
  nodeIds: readonly string[]
): { x: number; y: number; width: number; height: number } | null {
  const wanted = new Set(nodeIds)
  let minX = Number.POSITIVE_INFINITY
  let minY = Number.POSITIVE_INFINITY
  let maxX = Number.NEGATIVE_INFINITY
  let maxY = Number.NEGATIVE_INFINITY
  for (const node of nodes) {
    if (!node.id || !wanted.has(node.id)) continue
    const width = node.dimensions?.width ?? node.measured?.width ?? node.width ?? 120
    const height = node.dimensions?.height ?? node.measured?.height ?? node.height ?? 40
    const origin = node.computedPosition ?? node.position
    const x = origin?.x ?? 0
    const y = origin?.y ?? 0
    const boxWidth = Number(width) || 120
    const boxHeight = Number(height) || 40
    minX = Math.min(minX, x)
    minY = Math.min(minY, y)
    maxX = Math.max(maxX, x + boxWidth)
    maxY = Math.max(maxY, y + boxHeight)
  }
  if (!Number.isFinite(minX) || !Number.isFinite(minY)) return null
  return {
    x: minX,
    y: minY,
    width: Math.max(1, maxX - minX),
    height: Math.max(1, maxY - minY),
  }
}
