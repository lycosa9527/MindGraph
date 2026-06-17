import type { DiagramNode } from '@/types'
import type { MindGraphNode } from '@/types/vueflow'

export type MindMapNavDirection = 'up' | 'down' | 'left' | 'right'

const DIRECTION_VECTORS: Record<MindMapNavDirection, { x: number; y: number }> = {
  up: { x: 0, y: -1 },
  down: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
}

export interface MindMapNavNodeRect {
  id: string
  cx: number
  cy: number
}

function resolveNodeSize(
  node: DiagramNode,
  dimensions: Record<string, { width: number; height: number }>,
  mindMapWidths: Record<string, number>,
  mindMapHeights: Record<string, number>
): { width: number; height: number } {
  const fromDom = dimensions[node.id]
  if (fromDom) return fromDom
  const w = mindMapWidths[node.id]
  const h = mindMapHeights[node.id]
  if (w != null && h != null) return { width: w, height: h }
  if (node.id === 'topic') return { width: 120, height: 48 }
  return { width: 100, height: 36 }
}

export function buildMindMapNavRectsFromLayout(
  nodes: MindGraphNode[],
  getSize: (nodeId: string) => { width: number; height: number } | undefined
): MindMapNavNodeRect[] {
  return nodes.map((node) => {
    const measured = getSize(node.id)
    const width = measured?.width ?? (node.id === 'topic' ? 120 : 100)
    const height = measured?.height ?? (node.id === 'topic' ? 48 : 36)
    return {
      id: node.id,
      cx: node.position.x + width / 2,
      cy: node.position.y + height / 2,
    }
  })
}

export function buildMindMapNavRects(
  nodes: DiagramNode[],
  dimensions: Record<string, { width: number; height: number }>,
  mindMapWidths: Record<string, number>,
  mindMapHeights: Record<string, number>
): MindMapNavNodeRect[] {
  return nodes
    .filter((node) => node.position)
    .map((node) => {
      const { width, height } = resolveNodeSize(
        node,
        dimensions,
        mindMapWidths,
        mindMapHeights
      )
      const x = node.position?.x ?? 0
      const y = node.position?.y ?? 0
      return {
        id: node.id,
        cx: x + width / 2,
        cy: y + height / 2,
      }
    })
}

/**
 * Pick the nearest node in a screen direction using center-to-center Euclidean distance,
 * restricted to the forward half-plane for that direction.
 */
export function findMindMapNodeInDirection(
  currentId: string,
  direction: MindMapNavDirection,
  rects: MindMapNavNodeRect[]
): string | null {
  if (rects.length === 0) return null

  const current = rects.find((r) => r.id === currentId) ?? rects[0]
  const dir = DIRECTION_VECTORS[direction]

  let bestId: string | null = null
  let bestDist = Infinity

  for (const candidate of rects) {
    if (candidate.id === current.id) continue

    const dx = candidate.cx - current.cx
    const dy = candidate.cy - current.cy
    const dot = dx * dir.x + dy * dir.y
    if (dot <= 0) continue

    const dist = Math.hypot(dx, dy)
    if (dist < bestDist) {
      bestDist = dist
      bestId = candidate.id
    }
  }

  return bestId
}

export function resolveMindMapNavStartId(
  selectedIds: string[],
  rects: MindMapNavNodeRect[]
): string | null {
  if (selectedIds.length > 0 && rects.some((r) => r.id === selectedIds[0])) {
    return selectedIds[0]
  }
  const topic = rects.find((r) => r.id === 'topic')
  if (topic) return topic.id
  return rects[0]?.id ?? null
}

export function mindMapArrowKeyToDirection(key: string): MindMapNavDirection | null {
  switch (key) {
    case 'ArrowUp':
      return 'up'
    case 'ArrowDown':
      return 'down'
    case 'ArrowLeft':
      return 'left'
    case 'ArrowRight':
      return 'right'
    default:
      return null
  }
}

export function isMindMapDiagramType(type: string | null | undefined): boolean {
  return type === 'mindmap' || type === 'mind_map'
}
