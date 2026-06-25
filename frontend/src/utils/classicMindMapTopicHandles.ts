import type { Connection, DiagramNode } from '@/types'

export function parseMindMapSideHandleIndex(sourceHandle: string | undefined): number {
  if (!sourceHandle) return 0
  const match = sourceHandle.match(/^mindmap-(?:left|right)-(\d+)$/)
  return match ? parseInt(match[1], 10) : 0
}

function parseBranchSiblingIndex(nodeId: string): number {
  const match = nodeId.match(/^branch-[lr]-\d+-(\d+)$/)
  return match ? parseInt(match[1], 10) : 0
}

/** Topic→branch edges on one side, in stable layout order. */
export function classicMindMapTopicSideConnections(
  connections: Connection[],
  side: 'l' | 'r',
  nodes: DiagramNode[] = []
): Connection[] {
  const branchPrefix = `branch-${side}-`
  const nodeById = new Map(nodes.map((node) => [node.id, node]))

  return connections
    .filter((c) => c.source === 'topic' && c.target.startsWith(branchPrefix))
    .slice()
    .sort((a, b) => {
      const bySibling = parseBranchSiblingIndex(a.target) - parseBranchSiblingIndex(b.target)
      if (bySibling !== 0) return bySibling

      const aY = nodeById.get(a.target)?.position?.y ?? 0
      const bY = nodeById.get(b.target)?.position?.y ?? 0
      if (aY !== bY) return aY - bY

      return parseMindMapSideHandleIndex(a.sourceHandle) - parseMindMapSideHandleIndex(b.sourceHandle)
    })
}

/**
 * Classic topic handles: evenly spaced along each edge (baseline c2611060e).
 * One sequential handle id per branch on that side so vue-flow never falls back to center.
 */
export function classicMindMapSideHandleTopPercent(index: number, count: number): number {
  return ((index + 1) / (count + 1)) * 100
}

/**
 * Horizontal inset from the topic pill bbox to the visible left/right semicircle at `topPercent`.
 * Wide pill topics only expose a semicircular cap — bbox corners sit outside the fill.
 */
export function classicMindMapPillHandleInsetPx(nodeHeightPx: number, topPercent: number): number {
  if (nodeHeightPx <= 0) return 0
  const radius = nodeHeightPx / 2
  const y = (topPercent / 100) * nodeHeightPx
  const dy = y - radius
  if (Math.abs(dy) >= radius) return radius
  return radius - Math.sqrt(radius * radius - dy * dy)
}

function classicMindMapTopicHandleTransform(
  side: 'l' | 'r',
  topPercent: number,
  nodeHeightPx?: number | null
): string {
  const inset =
    nodeHeightPx != null && nodeHeightPx > 0
      ? classicMindMapPillHandleInsetPx(nodeHeightPx, topPercent)
      : 0
  if (inset <= 0) return 'translateY(-50%)'
  const shiftPx = side === 'l' ? inset : -inset
  return `translate(${shiftPx}px, -50%)`
}

export function buildClassicMindMapTopicHandlePositions(
  connections: Connection[],
  side: 'l' | 'r',
  prefix: string,
  nodes: DiagramNode[] = [],
  nodeHeightPx?: number | null
): Array<{ id: string; top: string; transform: string }> {
  const count = classicMindMapTopicSideConnections(connections, side, nodes).length
  if (count === 0) return []

  return Array.from({ length: count }, (_, index) => {
    const topPercent = classicMindMapSideHandleTopPercent(index, count)
    return {
      id: `${prefix}-${index}`,
      top: `${topPercent}%`,
      transform: classicMindMapTopicHandleTransform(side, topPercent, nodeHeightPx),
    }
  })
}

/** Align topic edge sourceHandle with the evenly spaced handle ids for that side. */
export function withClassicMindMapTopicSourceHandle(
  conn: Connection,
  connections: Connection[],
  nodes: DiagramNode[] = []
): Connection {
  if (conn.source !== 'topic') return conn

  const side: 'l' | 'r' | null = conn.target.startsWith('branch-l-')
    ? 'l'
    : conn.target.startsWith('branch-r-')
      ? 'r'
      : null
  if (!side) return conn

  const prefix = side === 'r' ? 'mindmap-right' : 'mindmap-left'
  const ordered = classicMindMapTopicSideConnections(connections, side, nodes)
  const index = ordered.findIndex((edge) => edge.id === conn.id)
  if (index < 0) return conn

  return { ...conn, sourceHandle: `${prefix}-${index}` }
}
