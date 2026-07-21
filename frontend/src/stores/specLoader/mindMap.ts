/**
 * Mind Map Loader
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_MINDMAP_RANK_SEPARATION,
  DEFAULT_NODE_WIDTH,
  MINDMAP_TARGET_EXTENT,
} from '@/composables/diagrams/layoutConfig'
import { resolveMindMapTopicBorderColor } from '@/config/mindMapGeometry'
import { readMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'
import { readMindMapNodeUid } from '@/utils/mindMapNodeUid'
import type { Connection, DiagramNode } from '@/types'

import { mindMapNodePathKey } from '@/stores/diagram/mindMapStylePreservation'

import { layoutMindMapSideLegacy } from './mindMapLegacyLayout'
import type { MindMapBranchSpec } from './mindMapLegacyLayout'
import {
  estimateNodeWidthForCanvasMode,
  estimateTopicNodeHeightForCanvasMode,
  estimateTopicNodeWidthForCanvasMode,
  measureBranchNodeHeightForCanvasMode,
} from './mindMapMeasurements'
import { layoutMindMapSideV2 } from './mindMapV2Layout'
import type { SpecLoaderResult } from './types'
import {
  estimateNodeWidthWithTypography,
  estimateTopicNodeHeightWithTypography,
  estimateTopicNodeWidthWithTypography,
  hasCustomMindMapTypography,
  measureBranchNodeHeightWithTypography,
  measureBranchNodeUnderlineHeightWithTypography,
  measureMindMapUnderlineBoxMetricsWithTypography,
  type MindMapMeasureTypography,
} from './mindMapTypographyMeasure'
import {
  measureMindMapUnderlineBoxMetrics as measureMindMapUnderlineBoxMetricsForCanvasMode,
} from './mindMapMeasurements'

export type { MindMapMeasureTypography }
export type MindMapBranch = MindMapBranchSpec

function activeCanvasMode(): 'legacy' | 'v2' {
  return readMindMapV2VisualDesignActive() ? 'v2' : 'legacy'
}

export function estimateNodeWidth(
  text: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): number {
  if (hasCustomMindMapTypography(typography)) {
    return estimateNodeWidthWithTypography(text, nodeId, typography)
  }
  return estimateNodeWidthForCanvasMode(text, nodeId, activeCanvasMode())
}

export function measureBranchNodeHeight(
  text: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): number {
  if (hasCustomMindMapTypography(typography)) {
    return measureBranchNodeHeightWithTypography(text, nodeId, typography)
  }
  return measureBranchNodeHeightForCanvasMode(text, nodeId, activeCanvasMode())
}

export function measureBranchNodeUnderlineHeight(
  text: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): number {
  return measureMindMapUnderlineBoxMetrics(text, nodeId, typography).totalHeight
}

export function measureMindMapUnderlineBoxMetrics(
  text: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): { textBlockHeight: number; totalHeight: number; lineMidlineOffsetFromTop: number } {
  if (hasCustomMindMapTypography(typography)) {
    return measureMindMapUnderlineBoxMetricsWithTypography(text, nodeId, typography)
  }
  return measureMindMapUnderlineBoxMetricsForCanvasMode(text, nodeId)
}

export function estimateTopicNodeWidth(
  text: string,
  typography?: MindMapMeasureTypography
): number {
  if (hasCustomMindMapTypography(typography)) {
    return estimateTopicNodeWidthWithTypography(text, typography)
  }
  return estimateTopicNodeWidthForCanvasMode(text, activeCanvasMode())
}

export function estimateTopicNodeHeight(
  text: string,
  typography?: MindMapMeasureTypography
): number {
  if (hasCustomMindMapTypography(typography)) {
    return estimateTopicNodeHeightWithTypography(text, typography)
  }
  return estimateTopicNodeHeightForCanvasMode(text, activeCanvasMode())
}

/**
 * Distribute branches clockwise matching Python agent logic.
 */
export function distributeBranchesClockwise(branches: MindMapBranch[]): {
  rightBranches: MindMapBranch[]
  leftBranches: MindMapBranch[]
} {
  const total = branches.length
  const midPoint = Math.ceil(total / 2)

  const rightBranches = branches.slice(0, midPoint)
  const leftBranches = branches.slice(midPoint).reverse()

  return { rightBranches, leftBranches }
}

/**
 * Normalize horizontal extent so left and right sides have equal curve length from center.
 */
export function normalizeMindMapHorizontalSymmetry(
  nodes: DiagramNode[],
  centerX: number,
  minExtent: number = DEFAULT_MINDMAP_RANK_SEPARATION
): void {
  const leftNodes = nodes.filter((n) => n.type === 'branch' && n.id.startsWith('branch-l-'))
  const rightNodes = nodes.filter((n) => n.type === 'branch' && n.id.startsWith('branch-r-'))

  if (leftNodes.length === 0 && rightNodes.length === 0) return

  const getNodeWidth = (node: DiagramNode): number =>
    (node.data?.estimatedWidth as number) || DEFAULT_NODE_WIDTH
  const getCenterX = (node: DiagramNode): number => (node.position?.x ?? 0) + getNodeWidth(node) / 2

  function scaleNodeX(
    node: DiagramNode,
    topicCenterX: number,
    scale: number,
    side: 'left' | 'right'
  ): void {
    if (!node.position) return
    const nodeWidth = getNodeWidth(node)
    const center = getCenterX(node)
    const distFromCenter = side === 'left' ? topicCenterX - center : center - topicCenterX
    const newCenter =
      side === 'left' ? topicCenterX - distFromCenter * scale : topicCenterX + distFromCenter * scale
    node.position.x = newCenter - nodeWidth / 2
  }

  let leftExtent = leftNodes.length > 0 ? centerX - Math.min(...leftNodes.map(getCenterX)) : 0
  let rightExtent = rightNodes.length > 0 ? Math.max(...rightNodes.map(getCenterX)) - centerX : 0

  const currentExtent = Math.min(leftExtent, rightExtent) || Math.max(leftExtent, rightExtent)
  if (currentExtent > 0 && currentExtent < MINDMAP_TARGET_EXTENT) {
    const scale = MINDMAP_TARGET_EXTENT / currentExtent
    leftNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'left'))
    rightNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'right'))
    leftExtent = leftExtent > 0 ? leftExtent * scale : 0
    rightExtent = rightExtent > 0 ? rightExtent * scale : 0
  }

  const leftExpanded = leftExtent > 0 && leftExtent < minExtent
  const rightExpanded = rightExtent > 0 && rightExtent < minExtent
  if (leftExpanded) {
    const scale = minExtent / leftExtent
    leftNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'left'))
    leftExtent = minExtent
  }
  if (rightExpanded) {
    const scale = minExtent / rightExtent
    rightNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'right'))
    rightExtent = minExtent
  }

  const targetExtent = Math.max(leftExtent, rightExtent) || Math.min(leftExtent, rightExtent)
  if (targetExtent <= 0) return

  if (leftExtent > 0 && leftExtent < targetExtent) {
    const scale = targetExtent / leftExtent
    leftNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'left'))
  }

  if (rightExtent > 0 && rightExtent < targetExtent) {
    const scale = targetExtent / rightExtent
    rightNodes.forEach((node) => scaleNodeX(node, centerX, scale, 'right'))
  }
}

export function nodesAndConnectionsToMindMapSpec(
  nodes: DiagramNode[],
  connections: Connection[]
): { topic: string; leftBranches: MindMapBranch[]; rightBranches: MindMapBranch[] } {
  const topicNode = nodes.find((n) => n.id === 'topic')
  const topic = topicNode?.text ?? ''

  const childrenMap = new Map<string, string[]>()
  connections.forEach((c) => {
    if (!childrenMap.has(c.source)) {
      childrenMap.set(c.source, [])
    }
    const sourceChildren = childrenMap.get(c.source)
    if (sourceChildren) {
      sourceChildren.push(c.target)
    }
  })

  const nodeMap = new Map(nodes.map((n) => [n.id, n]))

  const sortByGlobalIndex = sortMindMapNodeIdsByGlobalIndex

  function buildBranch(nodeId: string): MindMapBranch | null {
    const node = nodeMap.get(nodeId)
    if (!node || nodeId === 'topic') return null
    const childIds = (childrenMap.get(nodeId) ?? []).slice().sort(sortByGlobalIndex)
    const children = childIds
      .map((id) => buildBranch(id))
      .filter((b): b is MindMapBranch => b !== null)
    const uid = readMindMapNodeUid(node) ?? undefined
    return {
      text: node.text ?? '',
      uid,
      children: children.length > 0 ? children : undefined,
    }
  }

  const topicChildIds = childrenMap.get('topic') ?? []
  const rightIds = topicChildIds.filter((id) => id.startsWith('branch-r-')).sort(sortByGlobalIndex)
  const leftIds = topicChildIds.filter((id) => id.startsWith('branch-l-')).sort(sortByGlobalIndex)

  const rightBranches = rightIds
    .map((id) => buildBranch(id))
    .filter((b): b is MindMapBranch => b !== null)
  const leftBranches = leftIds
    .map((id) => buildBranch(id))
    .filter((b): b is MindMapBranch => b !== null)

  return { topic, leftBranches, rightBranches }
}

export interface FindBranchResult {
  branch: MindMapBranch
  parentArray: MindMapBranch[]
  indexInParent: number
}

export function sortMindMapNodeIdsByGlobalIndex(a: string, b: string): number {
  const aIdx = parseInt(a.split('-')[3] ?? '0', 10)
  const bIdx = parseInt(b.split('-')[3] ?? '0', 10)
  return aIdx - bIdx
}

function buildMindMapChildrenMap(connections: Connection[]): Map<string, string[]> {
  const childrenMap = new Map<string, string[]>()
  connections.forEach((c) => {
    if (!childrenMap.has(c.source)) {
      childrenMap.set(c.source, [])
    }
    const sourceChildren = childrenMap.get(c.source)
    if (sourceChildren) {
      sourceChildren.push(c.target)
    }
  })
  return childrenMap
}

function findBranchByPathKey(
  rightBranches: MindMapBranch[],
  leftBranches: MindMapBranch[],
  pathKey: string
): FindBranchResult | null {
  const slash = pathKey.indexOf('/')
  if (slash < 0) return null
  const side = pathKey.slice(0, slash)
  if (side !== 'l' && side !== 'r') return null
  const indexParts = pathKey
    .slice(slash + 1)
    .split('/')
    .filter((part) => part.length > 0)
  const indices = indexParts.map((part) => parseInt(part, 10))
  if (indices.length === 0 || indices.some((n) => Number.isNaN(n))) return null

  let parentArray = side === 'l' ? leftBranches : rightBranches
  let branch: MindMapBranch | null = null
  for (let depth = 0; depth < indices.length; depth += 1) {
    const idx = indices[depth]
    if (idx < 0 || idx >= parentArray.length) return null
    branch = parentArray[idx]
    if (depth < indices.length - 1) {
      const children = branch.children
      if (!children || children.length === 0) return null
      parentArray = children
    }
  }
  if (!branch) return null
  return { branch, parentArray, indexInParent: indices[indices.length - 1] }
}

/** Resolve a branch spec entry by the diagram's actual node id (not a regenerated counter). */
export function findBranchByNodeId(
  rightBranches: MindMapBranch[],
  leftBranches: MindMapBranch[],
  nodeId: string,
  connections: Connection[]
): FindBranchResult | null {
  const childrenMap = buildMindMapChildrenMap(connections)
  let result: FindBranchResult | null = null

  function walkLevel(
    nodeIds: string[],
    branches: MindMapBranch[],
    parentArray: MindMapBranch[]
  ): boolean {
    const limit = Math.min(nodeIds.length, branches.length)
    for (let i = 0; i < limit; i++) {
      const currentId = nodeIds[i]
      if (currentId === nodeId) {
        result = { branch: branches[i], parentArray, indexInParent: i }
        return true
      }
      const childIds = (childrenMap.get(currentId) ?? [])
        .slice()
        .sort(sortMindMapNodeIdsByGlobalIndex)
      const childBranches = branches[i].children
      if (childIds.length > 0 && childBranches && childBranches.length > 0) {
        if (walkLevel(childIds, childBranches, childBranches)) {
          return true
        }
      }
    }
    return false
  }

  const topicChildIds = childrenMap.get('topic') ?? []
  const rightIds = topicChildIds
    .filter((id) => id.startsWith('branch-r-'))
    .sort(sortMindMapNodeIdsByGlobalIndex)
  const leftIds = topicChildIds
    .filter((id) => id.startsWith('branch-l-'))
    .sort(sortMindMapNodeIdsByGlobalIndex)

  if (walkLevel(rightIds, rightBranches, rightBranches)) return result
  if (walkLevel(leftIds, leftBranches, leftBranches)) return result

  const pathKey = mindMapNodePathKey(nodeId, connections)
  if (pathKey && pathKey !== 'topic') {
    return findBranchByPathKey(rightBranches, leftBranches, pathKey)
  }
  return null
}

export function loadMindMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const topic = (spec.topic as string) || (spec.central_topic as string) || ''

  let rightBranches: MindMapBranch[]
  let leftBranches: MindMapBranch[]

  if (spec.preserveLeftRight && spec.leftBranches && spec.rightBranches) {
    rightBranches = spec.rightBranches as MindMapBranch[]
    leftBranches = spec.leftBranches as MindMapBranch[]
  } else if (spec.leftBranches || spec.left || spec.rightBranches || spec.right) {
    const left = (spec.leftBranches as MindMapBranch[]) || (spec.left as MindMapBranch[]) || []
    const right = (spec.rightBranches as MindMapBranch[]) || (spec.right as MindMapBranch[]) || []
    const allBranches = [...left, ...right]
    const distributed = distributeBranchesClockwise(allBranches)
    rightBranches = distributed.rightBranches
    leftBranches = distributed.leftBranches
  } else if (Array.isArray(spec.children)) {
    const allBranches = spec.children as MindMapBranch[]
    const distributed = distributeBranchesClockwise(allBranches)
    rightBranches = distributed.rightBranches
    leftBranches = distributed.leftBranches
  } else {
    rightBranches = []
    leftBranches = []
  }

  const allBranches = [...rightBranches, ...leftBranches]
  const v2Visuals = readMindMapV2VisualDesignActive()
  const canvasMode = v2Visuals ? 'v2' : 'legacy'

  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const rankSeparation = DEFAULT_MINDMAP_RANK_SEPARATION

  const topicWidth = estimateTopicNodeWidthForCanvasMode(topic, canvasMode)
  const topicEstimatedHeight = estimateTopicNodeHeightForCanvasMode(topic, canvasMode)

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  const topicNode: DiagramNode = {
    id: 'topic',
    text: topic,
    type: 'topic',
    position: {
      x: centerX - topicWidth / 2,
      y: centerY - topicEstimatedHeight / 2,
    },
    data: {
      totalBranchCount: allBranches.length,
      estimatedWidth: topicWidth,
      estimatedHeight: topicEstimatedHeight,
    },
  }
  nodes.push(topicNode)

  if (v2Visuals) {
    const topicBorderColor = resolveMindMapTopicBorderColor(topicNode)
    const diagramStyleId =
      (spec._mindmap_diagram_style as string | undefined) ??
      (spec.mindmap_diagram_style as string | undefined)
    layoutMindMapSideV2(
      rightBranches,
      'right',
      centerX,
      centerY,
      topicWidth,
      rankSeparation,
      nodes,
      connections,
      0,
      allBranches.length,
      topicBorderColor,
      diagramStyleId
    )
    layoutMindMapSideV2(
      leftBranches,
      'left',
      centerX,
      centerY,
      topicWidth,
      rankSeparation,
      nodes,
      connections,
      rightBranches.length,
      allBranches.length,
      topicBorderColor,
      diagramStyleId
    )
  } else {
    layoutMindMapSideLegacy(
      rightBranches,
      'right',
      centerX,
      centerY,
      topicWidth,
      rankSeparation,
      nodes,
      connections,
      0,
      allBranches.length
    )
    layoutMindMapSideLegacy(
      leftBranches,
      'left',
      centerX,
      centerY,
      topicWidth,
      rankSeparation,
      nodes,
      connections,
      rightBranches.length,
      allBranches.length
    )
  }

  if (topicNode.position) {
    const topicCurrentCenterX = topicNode.position.x + topicWidth / 2
    const topicCurrentCenterY = topicNode.position.y + topicEstimatedHeight / 2
    const offsetXToCenter = centerX - topicCurrentCenterX
    const offsetYToCenter = centerY - topicCurrentCenterY
    nodes.forEach((node) => {
      if (node.position) {
        node.position.x += offsetXToCenter
        node.position.y += offsetYToCenter
      }
    })
  }

  return { nodes, connections }
}
