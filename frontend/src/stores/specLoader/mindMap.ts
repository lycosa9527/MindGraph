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
import {
  getMindMapDiagramStyleById,
  mindMapNodeShapeFromPreset,
} from '@/config/mindMapDiagramStyles'
import { resolveMindMapTopicBorderColor } from '@/config/mindMapGeometry'
import {
  buildMindMapChildrenMapByConnectionOrder,
  mindMapNodePathKey,
} from '@/stores/diagram/mindMapStylePreservation'
import type { MindMapCanvasMode } from '@/stores/ui'
import type { Connection, DiagramNode } from '@/types'
import {
  isMindMapBranchNumberingEnabled,
  resolveMindMapBranchNumberingNested,
  resolveMindMapBranchNumberingPrefix,
} from '@/utils/mindMapBranchNumbering'
import { readMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'
import { MINDMAP_LEGACY_ID_DATA_KEY } from '@/utils/mindMapIdentityMigrate'
import { isLeftoverMindMapBranchId, mindMapNodeSide } from '@/utils/mindMapLocation'
import { hydrateMindMapBranchTree, readMindMapNodeUid } from '@/utils/mindMapNodeUid'
import type { NodeShape } from '@/utils/nodeShapeStyle'

import { layoutMindMapSideLegacy } from './mindMapLegacyLayout'
import type { MindMapBranchSpec } from './mindMapLegacyLayout'
import {
  estimateNumberedBranchBoxWidth,
  estimateNodeWidthForCanvasMode,
  estimateTopicNodeHeightForCanvasMode,
  estimateTopicNodeWidthForCanvasMode,
  measureBranchNodeHeightForCanvasMode,
  measureNumberedBranchHeightForCanvasMode,
  measureNumberedUnderlineBoxMetrics,
  resolveMindMapMeasureShape,
} from './mindMapMeasurements'
import { measureMindMapUnderlineBoxMetrics as measureMindMapUnderlineBoxMetricsForCanvasMode } from './mindMapMeasurements'
import {
  type MindMapMeasureTypography,
  estimateNodeWidthWithTypography,
  estimateTopicNodeHeightWithTypography,
  estimateTopicNodeWidthWithTypography,
  hasCustomMindMapTypography,
  measureBranchNodeHeightWithTypography,
  measureMindMapUnderlineBoxMetricsWithTypography,
  resolveShapeFromMeasureStyle,
} from './mindMapTypographyMeasure'
import { layoutMindMapSideV2 } from './mindMapV2Layout'
import type { SpecLoaderResult } from './types'

export type { MindMapMeasureTypography }
export type MindMapBranch = MindMapBranchSpec

function activeCanvasMode(): 'legacy' | 'v2' {
  return readMindMapV2VisualDesignActive() ? 'v2' : 'legacy'
}

export function estimateNodeWidth(
  text: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography,
  shape?: NodeShape | null
): number {
  const resolvedShape = resolveShapeFromMeasureStyle(typography, shape)
  if (hasCustomMindMapTypography(typography)) {
    return estimateNodeWidthWithTypography(text, nodeId, typography, resolvedShape)
  }
  return estimateNodeWidthForCanvasMode(text, nodeId, activeCanvasMode(), resolvedShape)
}

function numberedFontFromTypography(typography?: MindMapMeasureTypography): {
  fontSize?: number
  fontWeight?: string
  fontFamily?: string
} {
  const custom = typography?.fontSize
  let fontSize: number | undefined
  if (custom != null) {
    const parsed = typeof custom === 'number' ? custom : parseFloat(String(custom))
    if (Number.isFinite(parsed) && parsed > 0) fontSize = parsed
  }
  return {
    fontSize,
    fontWeight: typography?.fontWeight != null ? String(typography.fontWeight) : undefined,
    fontFamily: typography?.fontFamily,
  }
}

/** Box width for prefix chrome + body (``1.`` vs ``第一章`` use different advances). */
export function estimateNumberedBranchWidth(
  label: string,
  prefix: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography,
  shape?: NodeShape | null
): number {
  if (!prefix) {
    return estimateNodeWidth(label, nodeId, typography, shape)
  }
  return estimateNumberedBranchBoxWidth(
    label,
    prefix,
    nodeId,
    resolveShapeFromMeasureStyle(typography, shape),
    numberedFontFromTypography(typography)
  )
}

export function measureNumberedBranchHeight(
  label: string,
  prefix: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): number {
  if (!prefix) {
    return measureBranchNodeHeight(label, nodeId, typography)
  }
  return measureNumberedBranchHeightForCanvasMode(
    label,
    prefix,
    nodeId,
    'v2',
    numberedFontFromTypography(typography)
  )
}

export function measureNumberedBranchUnderlineHeight(
  label: string,
  prefix: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): number {
  if (!prefix) {
    return measureBranchNodeUnderlineHeight(label, nodeId, typography)
  }
  return measureNumberedUnderlineBoxMetrics(
    label,
    prefix,
    nodeId,
    numberedFontFromTypography(typography)
  ).totalHeight
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
  typography?: MindMapMeasureTypography,
  shape?: NodeShape | null
): number {
  const resolvedShape = resolveShapeFromMeasureStyle(typography, shape)
  if (hasCustomMindMapTypography(typography)) {
    return estimateTopicNodeWidthWithTypography(text, typography, resolvedShape)
  }
  return estimateTopicNodeWidthForCanvasMode(text, activeCanvasMode(), resolvedShape)
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
 * Rebuild clockwise order from side arrays (inverse of distributeBranchesClockwise).
 */
export function mindMapBranchesClockwiseOrder(
  rightBranches: MindMapBranch[],
  leftBranches: MindMapBranch[]
): MindMapBranch[] {
  return [...rightBranches, ...leftBranches.slice().reverse()]
}

/**
 * When every top-level branch sits on the left (right empty), redistributes
 * clockwise so the map is balanced again. Right-only maps are left alone —
 * that matches the intentional "right" structure mode.
 */
export function rebalanceMindMapBranchesIfLeftOnly(
  leftBranches: MindMapBranch[],
  rightBranches: MindMapBranch[]
): {
  leftBranches: MindMapBranch[]
  rightBranches: MindMapBranch[]
  redistributed: boolean
} {
  if (rightBranches.length > 0 || leftBranches.length === 0) {
    return { leftBranches, rightBranches, redistributed: false }
  }
  const distributed = distributeBranchesClockwise(
    mindMapBranchesClockwiseOrder(rightBranches, leftBranches)
  )
  return {
    leftBranches: distributed.leftBranches,
    rightBranches: distributed.rightBranches,
    redistributed: true,
  }
}

function sameMindMapBranchList(left: MindMapBranch[], right: MindMapBranch[]): boolean {
  if (left.length !== right.length) return false
  return left.every((branch, index) => {
    const other = right[index]
    if (!other) return false
    if (branch === other) return true
    const uid = typeof branch.uid === 'string' ? branch.uid : ''
    const otherUid = typeof other.uid === 'string' ? other.uid : ''
    return uid === otherUid && branch.text === other.text
  })
}

/**
 * After an L1 delete: if the map was two-sided, redistribute remaining branches
 * clockwise (5→4 keeps 1–2 right and 3+5 left). Right-only structure mode is
 * unchanged; left-only still splits across both sides.
 */
export function rebalanceMindMapBranchesAfterL1Delete(
  leftBranches: MindMapBranch[],
  rightBranches: MindMapBranch[],
  hadBothSidesBefore: boolean
): {
  leftBranches: MindMapBranch[]
  rightBranches: MindMapBranch[]
  redistributed: boolean
} {
  if (!hadBothSidesBefore) {
    return rebalanceMindMapBranchesIfLeftOnly(leftBranches, rightBranches)
  }
  const distributed = distributeBranchesClockwise(
    mindMapBranchesClockwiseOrder(rightBranches, leftBranches)
  )
  const redistributed =
    !sameMindMapBranchList(distributed.leftBranches, leftBranches) ||
    !sameMindMapBranchList(distributed.rightBranches, rightBranches)
  return {
    leftBranches: distributed.leftBranches,
    rightBranches: distributed.rightBranches,
    redistributed,
  }
}

/**
 * Normalize horizontal extent so left and right sides have equal curve length from center.
 */
export function normalizeMindMapHorizontalSymmetry(
  nodes: DiagramNode[],
  centerX: number,
  minExtent: number = DEFAULT_MINDMAP_RANK_SEPARATION
): void {
  const leftNodes = nodes.filter(
    (n) => n.type === 'branch' && mindMapNodeSide(n.id, { node: n, nodes }) === 'left'
  )
  const rightNodes = nodes.filter(
    (n) => n.type === 'branch' && mindMapNodeSide(n.id, { node: n, nodes }) === 'right'
  )

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
      side === 'left'
        ? topicCenterX - distFromCenter * scale
        : topicCenterX + distFromCenter * scale
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

  const childrenMap = buildMindMapChildrenMapByConnectionOrder(connections)
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))

  function buildBranch(nodeId: string): MindMapBranch | null {
    const node = nodeMap.get(nodeId)
    if (!node || nodeId === 'topic') return null
    const childIds = childrenMap.get(nodeId) ?? []
    const children = childIds
      .map((id) => buildBranch(id))
      .filter((b): b is MindMapBranch => b !== null)
    const storedUid = readMindMapNodeUid(node)
    const leftover = isLeftoverMindMapBranchId(nodeId)
    const uid = storedUid ?? (leftover ? undefined : nodeId)
    const storedLegacy = node.data?.[MINDMAP_LEGACY_ID_DATA_KEY]
    const legacyId =
      typeof storedLegacy === 'string' && storedLegacy.trim()
        ? storedLegacy.trim()
        : leftover
          ? nodeId
          : undefined
    return {
      text: node.text ?? '',
      uid,
      legacyId,
      children: children.length > 0 ? children : undefined,
    }
  }

  const topicChildIds = childrenMap.get('topic') ?? []
  const rightIds = topicChildIds.filter(
    (id) => mindMapNodeSide(id, { nodes, connections }) === 'right'
  )
  const leftIds = topicChildIds.filter(
    (id) => mindMapNodeSide(id, { nodes, connections }) === 'left'
  )

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

function buildMindMapChildrenMap(connections: Connection[]): Map<string, string[]> {
  return buildMindMapChildrenMapByConnectionOrder(connections)
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
      const childIds = childrenMap.get(currentId) ?? []
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
  const rightIds = topicChildIds.filter(
    (id) => mindMapNodeSide(id, { connections }) === 'right'
  )
  const leftIds = topicChildIds.filter((id) => mindMapNodeSide(id, { connections }) === 'left')

  if (walkLevel(rightIds, rightBranches, rightBranches)) return result
  if (walkLevel(leftIds, leftBranches, leftBranches)) return result

  const pathKey = mindMapNodePathKey(nodeId, connections)
  if (pathKey && pathKey !== 'topic') {
    return findBranchByPathKey(rightBranches, leftBranches, pathKey)
  }
  return null
}

export type LoadMindMapSpecOptions = {
  /**
   * Session-owned canvas mode. When omitted, falls back to the viewer UI preference
   * (editor mutation paths). Showcase / export must pass the session mode.
   */
  canvasMode?: MindMapCanvasMode
}

export function loadMindMapSpec(
  spec: Record<string, unknown>,
  options?: LoadMindMapSpecOptions
): SpecLoaderResult {
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
  hydrateMindMapBranchTree(rightBranches)
  hydrateMindMapBranchTree(leftBranches)
  const canvasMode: MindMapCanvasMode =
    options?.canvasMode ?? (readMindMapV2VisualDesignActive() ? 'v2' : 'legacy')
  const v2Visuals = canvasMode === 'v2'
  const diagramStyleId =
    (spec._mindmap_diagram_style as string | undefined) ??
    (spec.mindmap_diagram_style as string | undefined)
  const diagramStyle = getMindMapDiagramStyleById(diagramStyleId)
  const topicShape = v2Visuals
    ? mindMapNodeShapeFromPreset({ id: 'topic', type: 'topic' }, diagramStyle)
    : resolveMindMapMeasureShape(null)

  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const rankSeparation = DEFAULT_MINDMAP_RANK_SEPARATION

  const topicWidth = estimateTopicNodeWidthForCanvasMode(topic, canvasMode, topicShape)
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
    ...(v2Visuals ? { style: { nodeShape: topicShape } } : {}),
  }
  nodes.push(topicNode)

  if (v2Visuals) {
    const topicBorderColor = resolveMindMapTopicBorderColor(topicNode)
    const layoutNumbering = {
      enabled: isMindMapBranchNumberingEnabled(spec),
      prefixStyle: resolveMindMapBranchNumberingPrefix(spec._mindmap_branch_numbering_prefix),
      nestedStyle: resolveMindMapBranchNumberingNested(spec._mindmap_branch_numbering_nested),
    }
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
      diagramStyleId,
      layoutNumbering
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
      diagramStyleId,
      layoutNumbering
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
