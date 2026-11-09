/**
 * One paint box for a mind-map branch: font, shape, and horizontal chrome.
 * The Vue node and every estimator call this. Depth comes from the tree.
 * A UUID with no parent link is a child box, never a silent level 1.
 *
 * `createMindMapBranchPaintIndex` walks the edges once per layout pass.
 * Depth is memoized on that index, so each node is O(1) after the walk.
 */
import {
  type MindMapDiagramStylePreset,
  getMindMapDiagramStyleById,
  mindMapNodeShapeFromPreset,
} from '@/config/mindMapDiagramStyles'
import { MIND_MAP_GEOMETRY, mindMapNodeHorizontalExtra } from '@/config/mindMapGeometry'
import type { NodeStyle, NodeType } from '@/types'
import {
  MINDMAP_DEPTH_DATA_KEY,
  MINDMAP_TOPIC_ID,
  isMindMapTreeConnection,
  parsePositionalMindMapBranchId,
} from '@/utils/mindMapLocation'
import type { NodeShape } from '@/utils/nodeShapeStyle'

export interface MindMapBranchPaintBox {
  depth: number
  fontSize: number
  shape: NodeShape
  horizontalExtra: number
}

export type MindMapPaintNode = {
  id: string
  type?: string
  style?: NodeStyle | null
  data?: Record<string, unknown> | null
}

type TreeEdge = {
  source: string
  target: string
  sourceHandle?: string
  edgeType?: string
}

/** Child metrics when the id is not in the tree and is not positional. */
const CHILD_DEPTH_WHEN_UNKNOWN = 2
const DEPTH_WALK_LIMIT = 32

type DepthMemo = {
  parentOf: Map<string, string>
  depthOf: Map<string, number>
}

let presetKey: string | null | undefined
let presetCached: MindMapDiagramStylePreset | null = null

function parentMap(connections: readonly TreeEdge[] | null | undefined): DepthMemo {
  const parentOf = new Map<string, string>()
  if (connections) {
    for (const connection of connections) {
      if (!isMindMapTreeConnection(connection)) continue
      parentOf.set(connection.target, connection.source)
    }
  }
  return { parentOf, depthOf: new Map() }
}

function presetFor(diagramStyleId?: string | null): MindMapDiagramStylePreset {
  const key = diagramStyleId ?? null
  if (presetCached && presetKey === key) return presetCached
  presetKey = key
  presetCached = getMindMapDiagramStyleById(diagramStyleId)
  return presetCached
}

function stampedDepth(data: MindMapPaintNode['data']): number | null {
  const raw = data?.[MINDMAP_DEPTH_DATA_KEY]
  return typeof raw === 'number' && Number.isFinite(raw) && raw >= 0 ? raw : null
}

function explicitFontSize(style: NodeStyle | null | undefined): number | null {
  const custom = style?.fontSize
  if (custom == null) return null
  const parsed = typeof custom === 'number' ? custom : Number.parseFloat(String(custom))
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function walkedDepth(nodeId: string, memo: DepthMemo, guard = 0): number {
  const hit = memo.depthOf.get(nodeId)
  if (hit != null) return hit
  if (nodeId === MINDMAP_TOPIC_ID) {
    memo.depthOf.set(nodeId, 0)
    return 0
  }
  if (guard > DEPTH_WALK_LIMIT) return CHILD_DEPTH_WHEN_UNKNOWN
  const parent = memo.parentOf.get(nodeId)
  const depth = parent
    ? walkedDepth(parent, memo, guard + 1) + 1
    : (parsePositionalMindMapBranchId(nodeId)?.depth ?? CHILD_DEPTH_WHEN_UNKNOWN)
  memo.depthOf.set(nodeId, depth)
  return depth
}

function paintDepth(node: MindMapPaintNode, memo: DepthMemo): number {
  if (node.id === MINDMAP_TOPIC_ID || node.type === 'topic' || node.type === 'center') return 0
  return stampedDepth(node.data) ?? walkedDepth(node.id, memo)
}

function fontForDepth(depth: number, style: NodeStyle | null | undefined): number {
  const explicit = explicitFontSize(style)
  if (explicit != null) return explicit
  if (depth <= 0) return MIND_MAP_GEOMETRY.topicFontSize
  if (depth <= 1) return MIND_MAP_GEOMETRY.branchFontSize
  return MIND_MAP_GEOMETRY.fontSize
}

function boxFor(
  node: MindMapPaintNode,
  depth: number,
  preset: MindMapDiagramStylePreset
): MindMapBranchPaintBox {
  const style = node.style ?? undefined
  const shape =
    style?.nodeShape ??
    mindMapNodeShapeFromPreset(
      { id: node.id, type: (node.type ?? 'branch') as NodeType, data: node.data ?? undefined },
      preset,
      depth
    )
  return {
    depth,
    fontSize: fontForDepth(depth, style),
    shape,
    horizontalExtra: mindMapNodeHorizontalExtra(shape),
  }
}

export function mindMapBranchPaintBox(
  node: MindMapPaintNode,
  connections: readonly TreeEdge[] | null | undefined,
  diagramStyleId?: string | null
): MindMapBranchPaintBox {
  return boxFor(node, paintDepth(node, parentMap(connections)), presetFor(diagramStyleId))
}

/** One parent map for a layout pass. Depth after the first walk of a node is a map lookup. */
export function createMindMapBranchPaintIndex(
  connections: readonly TreeEdge[] | null | undefined,
  diagramStyleId?: string | null
): (node: MindMapPaintNode) => MindMapBranchPaintBox {
  const memo = parentMap(connections)
  const preset = presetFor(diagramStyleId)
  return (node) => boxFor(node, paintDepth(node, memo), preset)
}
