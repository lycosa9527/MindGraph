/**
 * Mind Map Loader
 */
import {
  BRANCH_NODE_HEIGHT,
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_MINDMAP_BRANCH_GAP,
  DEFAULT_MINDMAP_RANK_SEPARATION,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  MINDMAP_SIBLING_GAP,
  MINDMAP_TARGET_EXTENT,
} from '@/composables/diagrams/layoutConfig'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import {
  MIND_MAP_GEOMETRY,
  mindMapBranchFontSize,
  mindMapHorizontalPadding,
  mindMapNodeHorizontalExtra,
  mindMapUnderlineVerticalExtra,
  resolveMindMapTopicBorderColor,
} from '@/config/mindMapGeometry'
import { computeSymmetricRootStartYs } from '@/utils/mindMapSideStacking'
import { readMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'
import type { Connection, DiagramNode } from '@/types'

import {
  diagramLabelLikelyNeedsRenderedMeasure,
  measureRenderedDiagramLabelHeight,
  measureTextDimensions,
  measureTextWidth,
} from './textMeasurement'
import { computeScriptAwareMaxWidth } from './textMeasurementFallback'
import type { SpecLoaderResult } from './types'
import type { NodeStyle } from '@/types'

export type MindMapMeasureTypography = Pick<NodeStyle, 'fontSize' | 'fontWeight' | 'fontFamily'>

function resolveBranchFontSize(
  nodeId: string | undefined,
  typography?: MindMapMeasureTypography
): number {
  const custom = typography?.fontSize
  if (custom != null) {
    const n = typeof custom === 'number' ? custom : parseFloat(String(custom))
    if (Number.isFinite(n) && n > 0) return n
  }
  return mindMapBranchFontSize(nodeId)
}

function resolveTopicFontSize(typography?: MindMapMeasureTypography): number {
  const custom = typography?.fontSize
  if (custom != null) {
    const n = typeof custom === 'number' ? custom : parseFloat(String(custom))
    if (Number.isFinite(n) && n > 0) return n
  }
  return MIND_MAP_GEOMETRY.topicFontSize
}

function resolveMeasureFontWeight(
  typography: MindMapMeasureTypography | undefined,
  fallback: string
): string {
  if (typography?.fontWeight != null) return String(typography.fontWeight)
  return fallback
}

function measureOpts(typography?: MindMapMeasureTypography, fontWeight = 'normal') {
  return {
    fontWeight: resolveMeasureFontWeight(typography, fontWeight),
    fontFamily: typography?.fontFamily,
  }
}

interface MindMapBranch {
  text: string
  children?: MindMapBranch[]
}

/** Canonical field is text; accept label for backward compatibility with older specs */
function getBranchText(branch: { text?: string; label?: string }): string {
  return (branch.text ?? branch.label ?? '') as string
}

const BRANCH_BASE_MAX_TEXT_WIDTH = 200

/** Max text column width: single-line threshold when short, fixed cap when wrapping. */
function computeWrapMaxWidth(
  text: string,
  wrapThreshold: number,
  baseCap: number,
  fontSize: number,
  fontWeight = 'normal'
): number {
  if (typeof document === 'undefined') return wrapThreshold
  const tw = measureTextWidth(text, fontSize, { fontWeight })
  if (tw <= wrapThreshold) return wrapThreshold
  return baseCap
}

/**
 * Estimate rendered BranchNode width from text content.
 * Uses DOM-based measureTextWidth; wraps at a fixed cap when text exceeds threshold.
 */
export function estimateNodeWidth(
  text: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): number {
  if (!text) return MIND_MAP_GEOMETRY.minWidth
  const branchFontSize = resolveBranchFontSize(nodeId, typography)
  const shape = 'rounded' as const
  const nodeHorizontalExtra = mindMapNodeHorizontalExtra(shape)
  const minNodeWidth = MIND_MAP_GEOMETRY.minWidth
  const weight = resolveMeasureFontWeight(typography, 'normal')

  if (typeof document === 'undefined') {
    return Math.max(minNodeWidth, text.length * 8 + nodeHorizontalExtra)
  }

  const fullWidth = measureTextWidth(text, branchFontSize, measureOpts(typography, weight))
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
  const effectiveTextWidth =
    fullWidth > wrapThreshold ? BRANCH_BASE_MAX_TEXT_WIDTH : fullWidth

  void nodeId
  return Math.max(minNodeWidth, effectiveTextWidth + nodeHorizontalExtra)
}

const BRANCH_BORDER_Y = MIND_MAP_GEOMETRY.borderWidth * 2
const BRANCH_PADDING_Y = MIND_MAP_GEOMETRY.paddingY * 2

/**
 * Measure rendered BranchNode height using DOM measurement.
 * Font 14px, padding/border from MIND_MAP_GEOMETRY; min-height 34px.
 */
export function measureBranchNodeHeight(
  text: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): number {
  if (!text) return BRANCH_NODE_HEIGHT
  const branchFontSize = resolveBranchFontSize(nodeId, typography)
  const fontWeight = resolveMeasureFontWeight(typography, 'normal')
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
  const maxTextWidth = computeWrapMaxWidth(
    text,
    wrapThreshold,
    BRANCH_BASE_MAX_TEXT_WIDTH,
    branchFontSize,
    fontWeight
  )

  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    const contentH = measureRenderedDiagramLabelHeight(text, branchFontSize, maxTextWidth, {
      fontWeight,
      fontFamily: typography?.fontFamily,
    })
    return Math.max(BRANCH_NODE_HEIGHT, Math.ceil(contentH + BRANCH_PADDING_Y + BRANCH_BORDER_Y))
  }

  const { height: textHeight } = measureTextDimensions(text, branchFontSize, {
    maxWidth: maxTextWidth,
    paddingX: 0,
    paddingY: 0,
    fontWeight,
    fontFamily: typography?.fontFamily,
  })
  return Math.max(BRANCH_NODE_HEIGHT, textHeight + BRANCH_PADDING_Y + BRANCH_BORDER_Y)
}

/**
 * Height for underline-shaped branch nodes: text above the line, no box padding.
 */
export function measureBranchNodeUnderlineHeight(
  text: string,
  nodeId?: string,
  typography?: MindMapMeasureTypography
): number {
  const extra = mindMapUnderlineVerticalExtra()
  const branchFontSize = resolveBranchFontSize(nodeId, typography)
  const fontWeight = resolveMeasureFontWeight(typography, 'normal')
  const minHeight = branchFontSize + extra
  if (!text) return minHeight
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
  const maxTextWidth = computeWrapMaxWidth(
    text,
    wrapThreshold,
    BRANCH_BASE_MAX_TEXT_WIDTH,
    branchFontSize,
    fontWeight
  )

  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    const contentH = measureRenderedDiagramLabelHeight(text, branchFontSize, maxTextWidth, {
      fontWeight,
      fontFamily: typography?.fontFamily,
    })
    return Math.max(minHeight, Math.ceil(contentH + extra))
  }

  const { height: textHeight } = measureTextDimensions(text, branchFontSize, {
    maxWidth: maxTextWidth,
    paddingX: 0,
    paddingY: 0,
    fontWeight,
    fontFamily: typography?.fontFamily,
  })
  return Math.max(minHeight, textHeight + extra)
}

const TOPIC_CJK_REGEX =
  /[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]/g

const TOPIC_BASE_MAX_TEXT_WIDTH = 300

/**
 * Estimate rendered TopicNode width from text content.
 * Single-line width up to cap; fixed 300px column when wrapping.
 */
export function estimateTopicNodeWidth(
  text: string,
  typography?: MindMapMeasureTypography
): number {
  if (!text) return MIND_MAP_GEOMETRY.minWidth
  const topicFontSize = resolveTopicFontSize(typography)
  const topicPaddingX = MIND_MAP_GEOMETRY.paddingX * 2
  const topicBorderX = MIND_MAP_GEOMETRY.borderWidth * 2
  const minTopicWidth = MIND_MAP_GEOMETRY.minWidth
  const fontWeight = resolveMeasureFontWeight(typography, 'bold')

  if (typeof document === 'undefined') {
    const cjkMatches = text.match(TOPIC_CJK_REGEX)
    const cjkCount = cjkMatches ? cjkMatches.length : 0
    const otherCount = text.length - cjkCount
    const rawWidth = cjkCount * 19 + otherCount * 11
    return Math.max(
      minTopicWidth,
      Math.min(rawWidth, TOPIC_BASE_MAX_TEXT_WIDTH) + topicPaddingX + topicBorderX
    )
  }

  const fullWidth = measureTextWidth(text, topicFontSize, measureOpts(typography, fontWeight))
  const effectiveTextWidth =
    fullWidth > TOPIC_BASE_MAX_TEXT_WIDTH ? TOPIC_BASE_MAX_TEXT_WIDTH : fullWidth

  return Math.max(minTopicWidth, effectiveTextWidth + topicPaddingX + topicBorderX)
}

/**
 * Estimate rendered TopicNode height from text content.
 * Uses fixed max-width column; height from wrapped line count.
 */
export function estimateTopicNodeHeight(
  text: string,
  typography?: MindMapMeasureTypography
): number {
  if (!text) return MIND_MAP_GEOMETRY.minHeight
  const topicFontSize = resolveTopicFontSize(typography)
  const fontWeight = resolveMeasureFontWeight(typography, 'bold')
  const maxTextWidth = computeWrapMaxWidth(
    text,
    TOPIC_BASE_MAX_TEXT_WIDTH,
    TOPIC_BASE_MAX_TEXT_WIDTH,
    topicFontSize,
    fontWeight
  )
  const paddingY = MIND_MAP_GEOMETRY.paddingY * 2
  const borderY = MIND_MAP_GEOMETRY.borderWidth * 2

  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    const contentH = measureRenderedDiagramLabelHeight(text, topicFontSize, maxTextWidth, {
      fontWeight,
      fontFamily: typography?.fontFamily,
    })
    return Math.max(MIND_MAP_GEOMETRY.minHeight, Math.ceil(contentH + paddingY + borderY))
  }

  const { height: textHeight } = measureTextDimensions(text, topicFontSize, {
    fontWeight,
    fontFamily: typography?.fontFamily,
    maxWidth: maxTextWidth,
    paddingX: 0,
    paddingY: 0,
  })
  const lineHeight = Math.ceil(topicFontSize * 1.25)
  const numLines = Math.max(1, Math.ceil(textHeight / lineHeight))
  return Math.max(MIND_MAP_GEOMETRY.minHeight, numLines * lineHeight + paddingY + borderY)
}

/**
 * Distribute branches clockwise matching Python agent logic:
 * - First half → RIGHT side (top to bottom: Branch 1 top-right, Branch 2 bottom-right, etc.)
 * - Second half → LEFT side (reversed for clockwise: Branch 3 bottom-left, Branch 4 top-left, etc.)
 *
 * For 4 branches:
 * - Right: Branch 1 (top), Branch 2 (bottom)
 * - Left: Branch 3 (bottom), Branch 4 (top) - reversed order
 *
 * Returns branches organized by side and position
 */
export function distributeBranchesClockwise(branches: MindMapBranch[]): {
  rightBranches: MindMapBranch[]
  leftBranches: MindMapBranch[]
} {
  const total = branches.length
  const midPoint = Math.ceil(total / 2) // For odd numbers, right gets more

  // First half → RIGHT side (keep original order)
  const rightBranches = branches.slice(0, midPoint)

  // Second half → LEFT side (reverse for clockwise)
  const leftBranches = branches.slice(midPoint).reverse()

  return { rightBranches, leftBranches }
}

/**
 * Normalize horizontal extent so left and right sides have equal curve length from center.
 * Shrinks the side with greater extent to match the shorter side (avoids over-extending).
 * Expands the shorter side when below minExtent (fixes short curves after branch move).
 * Exported for use when loading saved mindmap diagrams (loadGenericSpec path).
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
    centerX: number,
    scale: number,
    side: 'left' | 'right'
  ): void {
    if (!node.position) return
    const nodeWidth = getNodeWidth(node)
    const center = getCenterX(node)
    const distFromCenter = side === 'left' ? centerX - center : center - centerX
    const newCenter =
      side === 'left' ? centerX - distFromCenter * scale : centerX + distFromCenter * scale
    node.position.x = newCenter - nodeWidth / 2
  }

  let leftExtent = leftNodes.length > 0 ? centerX - Math.min(...leftNodes.map(getCenterX)) : 0
  let rightExtent = rightNodes.length > 0 ? Math.max(...rightNodes.map(getCenterX)) - centerX : 0

  // Scale both sides up when extent is below target (e.g. after branch move)
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
  // Expand shorter side when below minimum (e.g. after branch move leaves one side sparse)
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

  // Expand smaller to match larger (never shrink) - same behavior as manual add
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

/**
 * Convert diagram nodes and connections back to mindmap spec.
 * Used when adding/removing nodes to rebuild and reload layout.
 */
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

  // ID format: branch-{side}-{depth}-{globalIndex}; sort by globalIndex to preserve layout order
  const sortByGlobalIndex = (a: string, b: string): number => {
    const aIdx = parseInt(a.split('-')[3] ?? '0', 10)
    const bIdx = parseInt(b.split('-')[3] ?? '0', 10)
    return aIdx - bIdx
  }

  function buildBranch(nodeId: string): MindMapBranch | null {
    const node = nodeMap.get(nodeId)
    if (!node || nodeId === 'topic') return null
    const childIds = (childrenMap.get(nodeId) ?? []).slice().sort(sortByGlobalIndex)
    const children = childIds
      .map((id) => buildBranch(id))
      .filter((b): b is MindMapBranch => b !== null)
    return {
      text: node.text ?? '',
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

/**
 * Find a branch in the spec tree by node ID (matches layout ID generation order).
 */
export function findBranchByNodeId(
  rightBranches: MindMapBranch[],
  leftBranches: MindMapBranch[],
  nodeId: string
): FindBranchResult | null {
  const counter = { value: 0 }
  let result: FindBranchResult | null = null

  function traverse(
    branches: MindMapBranch[],
    side: 'r' | 'l',
    depth: number,
    parentArray: MindMapBranch[]
  ): boolean {
    for (let i = 0; i < branches.length; i++) {
      const id = `branch-${side}-${depth}-${counter.value}`
      counter.value++
      if (id === nodeId) {
        result = { branch: branches[i], parentArray, indexInParent: i }
        return true
      }
      const childBranches = branches[i].children
      if (childBranches?.length) {
        if (traverse(childBranches, side, depth + 1, childBranches)) {
          return true
        }
      }
    }
    return false
  }

  if (traverse(rightBranches, 'r', 1, rightBranches)) return result
  counter.value = 0
  if (traverse(leftBranches, 'l', 1, leftBranches)) return result
  return null
}

/**
 * Simple stacking layout for one side of a mindmap.
 * Y: vertical stacking with parent centered on children.
 * X: each node is placed relative to its parent (subtree-balanced, no global depth columns).
 */
function layoutMindMapSideSimple(
  branches: MindMapBranch[],
  side: 'left' | 'right',
  topicCenterX: number,
  topicCenterY: number,
  topicWidth: number,
  rankSeparation: number,
  nodes: DiagramNode[],
  connections: Connection[],
  startHandleIndex: number,
  _totalBranches: number,
  topicBorderColor: string,
  v2Visuals: boolean
): void {
  if (branches.length === 0) return

  const sideChar = side === 'right' ? 'r' : 'l'

  interface LayoutNode {
    id: string
    text: string
    depth: number
    estimatedWidth: number
    estimatedHeight: number
    children: LayoutNode[]
    branchIndex: number
  }

  const globalCounter = { value: 0 }

  function buildTree(b: MindMapBranch, depth: number, branchIndex: number): LayoutNode {
    const idx = globalCounter.value++
    const id = `branch-${sideChar}-${depth}-${idx}`
    const text = getBranchText(b)
    const estimatedWidth = estimateNodeWidth(text, id)
    const estimatedHeight = measureBranchNodeHeight(text, id)
    const children = (b.children ?? []).map((c) => buildTree(c, depth + 1, branchIndex))
    return { id, text, depth, estimatedWidth, estimatedHeight, children, branchIndex }
  }

  const topLevel = branches.map((b, i) => {
    const branchIndex = side === 'right' ? i : startHandleIndex + i
    return buildTree(b, 1, branchIndex)
  })

  function subtreeHeight(node: LayoutNode): number {
    if (node.children.length === 0) return node.estimatedHeight
    const heights = node.children.map((c) => subtreeHeight(c))
    const childrenSpan =
      heights.reduce((a, b) => a + b, 0) + (node.children.length - 1) * MINDMAP_SIBLING_GAP
    return Math.max(node.estimatedHeight, childrenSpan)
  }

  const yPos = new Map<string, number>()

  function shiftDescendantPositions(node: LayoutNode, delta: number): void {
    for (const child of node.children) {
      const cur = yPos.get(child.id)
      if (cur !== undefined) yPos.set(child.id, cur + delta)
      shiftDescendantPositions(child, delta)
    }
  }

  function assignChildrenY(siblings: LayoutNode[], startY: number): number {
    let y = startY
    siblings.forEach((node, i) => {
      if (i > 0) y += MINDMAP_SIBLING_GAP
      if (node.children.length === 0) {
        yPos.set(node.id, y)
        y += node.estimatedHeight
      } else {
        const childEnd = assignChildrenY(node.children, y)
        const childrenSpan = childEnd - y

        if (childrenSpan >= node.estimatedHeight) {
          const firstChild = node.children[0]
          const lastChild = node.children[node.children.length - 1]
          const childTop = yPos.get(firstChild.id) ?? y
          const childBottom = (yPos.get(lastChild.id) ?? y) + lastChild.estimatedHeight
          const childCenter = (childTop + childBottom) / 2
          yPos.set(node.id, childCenter - node.estimatedHeight / 2)
          y = childEnd
        } else {
          const shift = (node.estimatedHeight - childrenSpan) / 2
          shiftDescendantPositions(node, shift)
          yPos.set(node.id, y)
          y += node.estimatedHeight
        }
      }
    })
    return y
  }

  const crossBranchGap = DEFAULT_MINDMAP_BRANCH_GAP

  function layoutSubtreeFromTop(node: LayoutNode, startY: number): number {
    if (node.children.length === 0) {
      yPos.set(node.id, startY)
      return startY + node.estimatedHeight
    }

    const childEnd = assignChildrenY(node.children, startY)
    const childrenSpan = childEnd - startY

    if (childrenSpan >= node.estimatedHeight) {
      const firstChild = node.children[0]
      const lastChild = node.children[node.children.length - 1]
      const childTop = yPos.get(firstChild.id) ?? startY
      const childBottom = (yPos.get(lastChild.id) ?? startY) + lastChild.estimatedHeight
      const childCenter = (childTop + childBottom) / 2
      yPos.set(node.id, childCenter - node.estimatedHeight / 2)
      return childEnd
    }

    const shift = (node.estimatedHeight - childrenSpan) / 2
    shiftDescendantPositions(node, shift)
    yPos.set(node.id, startY)
    return startY + node.estimatedHeight
  }

  const topLevelSpans = topLevel.map((node) => subtreeHeight(node))

  if (topLevel.length === 2) {
    const rootStartYs = computeSymmetricRootStartYs(topLevelSpans, topicCenterY, crossBranchGap)
    topLevel.forEach((node, i) => {
      layoutSubtreeFromTop(node, rootStartYs[i] ?? topicCenterY)
    })
  } else {
    const totalHeight =
      topLevelSpans.reduce((a, b) => a + b, 0) +
      Math.max(0, topLevel.length - 1) * crossBranchGap
    let y = topicCenterY - totalHeight / 2
    for (let i = 0; i < topLevel.length; i++) {
      y = layoutSubtreeFromTop(topLevel[i], y)
      if (i < topLevel.length - 1) y += crossBranchGap
    }
  }

  const topicOuterEdge =
    side === 'right' ? topicCenterX + topicWidth / 2 : topicCenterX - topicWidth / 2

  function createNodes(node: LayoutNode, parentOuterEdge: number): void {
    const y = yPos.get(node.id) ?? 0
    const x =
      side === 'right'
        ? parentOuterEdge + rankSeparation
        : parentOuterEdge - rankSeparation - node.estimatedWidth

    nodes.push({
      id: node.id,
      text: node.text,
      type: 'branch',
      position: { x, y },
      data: {
        branchIndex: node.branchIndex,
        estimatedWidth: node.estimatedWidth,
        estimatedHeight: node.estimatedHeight,
      },
    })

    const outerEdge = side === 'right' ? x + node.estimatedWidth : x
    node.children.forEach((c) => createNodes(c, outerEdge))
  }
  topLevel.forEach((n) => createNodes(n, topicOuterEdge))

  let handleIndex = 0

  function createConnections(node: LayoutNode, parentId: string): void {
    if (parentId === 'topic') {
      const sourceHandle = v2Visuals
        ? side === 'right'
          ? 'mindmap-right'
          : 'mindmap-left'
        : side === 'right'
          ? `mindmap-right-${handleIndex}`
          : `mindmap-left-${handleIndex}`
      const targetHandle = side === 'left' ? 'right-target' : 'left'
      const strokeColor = v2Visuals
        ? topicBorderColor
        : getMindmapBranchColor(node.branchIndex).border

      connections.push({
        id: `edge-topic-${node.id}`,
        source: 'topic',
        target: node.id,
        sourceHandle,
        targetHandle,
        style: { strokeColor },
      })
      if (!v2Visuals) {
        handleIndex++
      }
    } else {
      const isLeftSide = side === 'left'
      const strokeColor = v2Visuals
        ? topicBorderColor
        : getMindmapBranchColor(node.branchIndex).border

      connections.push({
        id: `edge-${parentId}-${node.id}`,
        source: parentId,
        target: node.id,
        sourceHandle: isLeftSide ? 'left-source' : 'right',
        targetHandle: isLeftSide ? 'right-target' : 'left',
        style: { strokeColor },
      })
    }
    node.children.forEach((c) => createConnections(c, node.id))
  }
  topLevel.forEach((n) => createConnections(n, 'topic'))
}

/**
 * Load mind map spec into diagram nodes and connections
 *
 * @param spec - Mind map spec with topic and branches
 * @returns SpecLoaderResult with nodes and connections
 */
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

  // Layout constants from layoutConfig
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  // Same rankSeparation for auto-complete and manual add so layout is identical
  const rankSeparation = DEFAULT_MINDMAP_RANK_SEPARATION

  const topicWidth = estimateTopicNodeWidth(topic)

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  const topicEstimatedHeight = estimateTopicNodeHeight(topic)

  // Topic node at center - position will be adjusted after branches are laid out
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

  const topicBorderColor = resolveMindMapTopicBorderColor(topicNode)
  const v2Visuals = readMindMapV2VisualDesignActive()

  // Layout right side branches
  layoutMindMapSideSimple(
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
    v2Visuals
  )

  // Layout left side branches
  layoutMindMapSideSimple(
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
    v2Visuals
  )

  // Step 4: Center entire layout so topic node is at canvas center
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
