/**
 * Compose a true vector SVG string from a mind-map snapshot.
 */
import { renderMindMapVectorEdges } from '@/utils/diagramMindMapVectorEdges'
import type { MindMapVectorSnapshot } from '@/utils/diagramMindMapVectorModel'
import { renderMindMapVectorNode } from '@/utils/diagramMindMapVectorNodes'

const VIEW_PADDING = 24

export type MindMapVectorSvgResult = {
  svg: string
  width: number
  height: number
  viewBox: { minX: number; minY: number; width: number; height: number }
}

export function computeMindMapVectorBounds(
  snapshot: MindMapVectorSnapshot,
  padding = VIEW_PADDING
): MindMapVectorSvgResult['viewBox'] {
  if (snapshot.nodes.length === 0) {
    return { minX: 0, minY: 0, width: 400, height: 300 }
  }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const node of snapshot.nodes) {
    minX = Math.min(minX, node.x)
    minY = Math.min(minY, node.y)
    maxX = Math.max(maxX, node.x + node.width)
    maxY = Math.max(maxY, node.y + node.height)
  }
  // Edges extend slightly past boxes; pad generously
  return {
    minX: minX - padding,
    minY: minY - padding,
    width: Math.max(1, maxX - minX + padding * 2),
    height: Math.max(1, maxY - minY + padding * 2),
  }
}

export function buildMindMapVectorSvg(snapshot: MindMapVectorSnapshot): MindMapVectorSvgResult {
  const viewBox = computeMindMapVectorBounds(snapshot)
  const edges = renderMindMapVectorEdges({
    connections: snapshot.connections,
    nodes: snapshot.nodes,
    canvasMode: snapshot.canvasMode,
    diagramStyleId: snapshot.diagramStyleId,
    outlineWireframe: snapshot.outlineWireframe,
    topicActualWidth: snapshot.topicActualWidth,
  })
  const nodes = snapshot.nodes
    .map((node) =>
      renderMindMapVectorNode(node, {
        diagramStyleId: snapshot.diagramStyleId,
        outlineWireframe: snapshot.outlineWireframe,
      })
    )
    .join('')

  const svg =
    `<?xml version="1.0" encoding="UTF-8"?>` +
    `<svg xmlns="http://www.w3.org/2000/svg" ` +
    `width="${viewBox.width}" height="${viewBox.height}" ` +
    `viewBox="${viewBox.minX} ${viewBox.minY} ${viewBox.width} ${viewBox.height}">` +
    `<rect x="${viewBox.minX}" y="${viewBox.minY}" width="${viewBox.width}" height="${viewBox.height}" fill="#ffffff"/>` +
    `<g class="mindmap-vector-edges">${edges}</g>` +
    `<g class="mindmap-vector-nodes">${nodes}</g>` +
    `</svg>`

  return {
    svg,
    width: viewBox.width,
    height: viewBox.height,
    viewBox,
  }
}

export function mindMapVectorSvgToDataUrl(svg: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}
