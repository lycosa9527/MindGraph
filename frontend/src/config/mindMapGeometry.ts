/**
 * Mind-map default geometric specifications (initial render & unstyled nodes).
 * Golden-ratio aesthetic baseline for typography, padding, borders, and edges.
 */
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'
import type { MindMapCanvasMode } from '@/stores/ui'

export const MIND_MAP_GEOMETRY = {
  /** Depth 2+ branch / leaf labels */
  fontSize: 14,
  /** Depth-1 (first-level) branch labels */
  branchFontSize: 16,
  /** Central topic default (bold weight applied in theme) */
  topicFontSize: 18,
  /** Primary UI sans — Inter with CJK fallbacks */
  fontFamily:
    "'Inter', 'Noto Sans SC', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif",
  /** Monospace for code markers / zoom readouts */
  monoFontFamily:
    "'JetBrains Mono', ui-monospace, 'Cascadia Code', 'SFMono-Regular', Consolas, monospace",
  borderWidth: 1.5,
  /** Default central-topic border (matches useTheme mindmap centralTopicStroke) */
  topicBorderColor: '#2563eb',
  /** Soft neutral border when theme does not override (eye-comfort gray) */
  defaultBorderColor: '#CBD5E1',
  /** Leaf / depth-2+ fill */
  leafBackgroundColor: '#FFFFFF',
  leafTextColor: '#334155',
  minWidth: 90,
  minHeight: 34,
  /** Horizontal padding per side (rounded / rectangle) */
  paddingX: 18,
  /** Horizontal padding per side (oval) */
  paddingXOval: 26,
  /** Vertical padding per side (18px total ≈ 9px × 2 with 14px text → min-height 34) */
  paddingY: 9,
  edgeStrokeWidth: 2,
  edgeStrokeOpacity: 0.7,
  edgeStrokeWidthHover: 3,
} as const

/** Parse depth from mind-map branch id (`branch-r-2-3` → 2). */
export function mindMapBranchDepth(nodeId: string): number {
  const match = nodeId.match(/^branch-[lr]-(\d+)-/)
  return match ? parseInt(match[1], 10) : 1
}

/** Parse clockwise global index from mind-map branch id (`branch-r-1-4` → 4). */
export function mindMapBranchGlobalIndex(nodeId: string): number | null {
  const match = nodeId.match(/^branch-[lr]-\d+-(\d+)$/)
  return match ? parseInt(match[1], 10) : null
}

/** Font size for a mind-map branch node by depth (L1 = 16, L2+ = 14). */
export function mindMapBranchFontSize(nodeId?: string): number {
  if (!nodeId?.startsWith('branch-')) return MIND_MAP_GEOMETRY.branchFontSize
  return mindMapBranchDepth(nodeId) <= 1
    ? MIND_MAP_GEOMETRY.branchFontSize
    : MIND_MAP_GEOMETRY.fontSize
}

/** Sort depth-2+ sibling branch ids by local layout index (same side / parent). */
export function sortMindMapChildIds(childIds: string[]): string[] {
  if (childIds.length <= 1) return childIds
  const hasIndexed = childIds.some((id) => mindMapBranchGlobalIndex(id) != null)
  if (!hasIndexed) return childIds
  return childIds.slice().sort((a, b) => {
    const ai = mindMapBranchGlobalIndex(a)
    const bi = mindMapBranchGlobalIndex(b)
    if (ai != null && bi != null) return ai - bi
    if (ai != null) return -1
    if (bi != null) return 1
    return 0
  })
}

/**
 * Sort topic's depth-1 children in clockwise order:
 * right side top→bottom, then left side bottom→top.
 * Per-side ids restart at 0, so never sort all children by id suffix alone.
 */
export function sortMindMapTopicChildIds(childIds: string[]): string[] {
  if (childIds.length <= 1) return childIds
  const right = childIds.filter((id) => id.startsWith('branch-r-'))
  const left = childIds.filter((id) => id.startsWith('branch-l-'))
  if (right.length === 0 && left.length === 0) return sortMindMapChildIds(childIds)

  right.sort(
    (a, b) => (mindMapBranchGlobalIndex(a) ?? 0) - (mindMapBranchGlobalIndex(b) ?? 0)
  )
  left.sort(
    (a, b) => (mindMapBranchGlobalIndex(b) ?? 0) - (mindMapBranchGlobalIndex(a) ?? 0)
  )
  return [...right, ...left]
}

export function mindMapHorizontalPadding(shape: 'rounded' | 'rectangle' | 'oval' | 'underline'): number {
  return shape === 'oval' ? MIND_MAP_GEOMETRY.paddingXOval : MIND_MAP_GEOMETRY.paddingX
}

export function mindMapNodeHorizontalExtra(
  shape: 'rounded' | 'rectangle' | 'oval' | 'underline'
): number {
  const px = mindMapHorizontalPadding(shape)
  const border = MIND_MAP_GEOMETRY.borderWidth
  return px * 2 + border * 2
}

export function mindMapNodeVerticalExtra(): number {
  const { paddingY, borderWidth } = MIND_MAP_GEOMETRY
  return paddingY * 2 + borderWidth * 2
}

/** Underline shape: line width matches mind-map edge stroke for seamless joins. */
export const MINDMAP_UNDERLINE_STROKE_WIDTH = MIND_MAP_GEOMETRY.edgeStrokeWidth

export function mindMapUnderlineContentPadding(): { top: number; textGap: number } {
  return { top: 2, textGap: 4 }
}

export function mindMapUnderlineVerticalExtra(): number {
  const { top, textGap } = mindMapUnderlineContentPadding()
  return top + textGap + MINDMAP_UNDERLINE_STROKE_WIDTH
}

/** Y coordinate where branch connectors meet the node (center or underline midline). */
export function mindMapConnectionAnchorY(
  nodeTopY: number,
  nodeHeight: number,
  shape: 'rounded' | 'rectangle' | 'oval' | 'underline'
): number {
  if (shape === 'underline') {
    return nodeTopY + nodeHeight - MINDMAP_UNDERLINE_STROKE_WIDTH / 2
  }
  return nodeTopY + nodeHeight / 2
}

/** Inverse of mindMapConnectionAnchorY: top-left Y so the connection anchor sits at anchorY. */
export function mindMapNodeTopYForAnchorY(
  anchorY: number,
  nodeHeight: number,
  shape: 'rounded' | 'rectangle' | 'oval' | 'underline'
): number {
  if (shape === 'underline') {
    return anchorY - nodeHeight + MINDMAP_UNDERLINE_STROKE_WIDTH / 2
  }
  return anchorY - nodeHeight / 2
}

/** Connection lines use the same color as the central topic border. */
export function resolveMindMapTopicBorderColor(
  topicNode?: Pick<DiagramNode, 'style'> | null
): string {
  return topicNode?.style?.borderColor || MIND_MAP_GEOMETRY.topicBorderColor
}

/** Apply topic border color to all mind-map connection strokes. */
export function syncMindMapConnectionStrokeColors(
  connections: Array<{ style?: { strokeColor?: string } }>,
  strokeColor: string
): void {
  connections.forEach((conn) => {
    conn.style = { ...(conn.style || {}), strokeColor }
  })
}

function branchIndexFromNode(node: DiagramNode | undefined): number | null {
  if (!node) return null
  const fromData = node.data?.branchIndex
  if (typeof fromData === 'number' && Number.isFinite(fromData)) {
    return fromData
  }
  return null
}

function branchIndexFromConnectionTree(
  startNodeId: string,
  nodeById: Map<string, DiagramNode>,
  parentByTarget: Map<string, string>
): number | null {
  let current: string | undefined = startNodeId
  while (current && current !== 'topic') {
    const fromNode = branchIndexFromNode(nodeById.get(current))
    if (fromNode != null) {
      return fromNode
    }
    current = parentByTarget.get(current)
  }
  return null
}

/** Classic canvas: per-branch palette stroke on curved connectors. */
export function resolveLegacyMindMapConnectionStrokeColor(
  connection: Connection,
  nodes: DiagramNode[],
  allConnections?: Connection[]
): string {
  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const targetIndex = branchIndexFromNode(nodeById.get(connection.target))
  if (targetIndex != null) {
    return getMindmapBranchColor(targetIndex).border
  }
  const sourceIndex = branchIndexFromNode(nodeById.get(connection.source))
  if (sourceIndex != null) {
    return getMindmapBranchColor(sourceIndex).border
  }

  if (allConnections?.length) {
    const parentByTarget = new Map<string, string>()
    for (const conn of allConnections) {
      parentByTarget.set(conn.target, conn.source)
    }
    const fromTree =
      branchIndexFromConnectionTree(connection.target, nodeById, parentByTarget) ??
      branchIndexFromConnectionTree(connection.source, nodeById, parentByTarget)
    if (fromTree != null) {
      return getMindmapBranchColor(fromTree).border
    }
  }

  return getMindmapBranchColor(0).border
}

/** Classic canvas: restore per-branch stroke colors on all connections. */
export function syncLegacyMindMapConnectionStrokeColors(
  connections: Connection[],
  nodes: DiagramNode[]
): void {
  for (const conn of connections) {
    conn.style = {
      ...(conn.style || {}),
      strokeColor: resolveLegacyMindMapConnectionStrokeColor(conn, nodes, connections),
    }
  }
}

/** Sync mind-map connection stroke colors for the active canvas mode. */
export function syncMindMapConnectionStrokeColorsForCanvasMode(
  connections: Connection[],
  nodes: DiagramNode[],
  mode: MindMapCanvasMode
): void {
  if (mode === 'v2') {
    const topic = nodes.find((node) => node.id === 'topic')
    syncMindMapConnectionStrokeColors(
      connections,
      resolveMindMapTopicBorderColor(topic)
    )
    return
  }
  syncLegacyMindMapConnectionStrokeColors(connections, nodes)
}
