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
import type { Connection, DiagramNode } from '@/types'

import {
  diagramLabelLikelyNeedsRenderedMeasure,
  measureRenderedDiagramLabelHeight,
  measureTextDimensions,
  measureTextWidth,
} from './textMeasurement'
import { computeScriptAwareMaxWidth } from './textMeasurementFallback'
import type { SpecLoaderResult } from './types'

interface MindMapBranch {
  text: string
  children?: MindMapBranch[]
}

/** Canonical field is text; accept label for backward compatibility with older specs */
function getBranchText(branch: { text?: string; label?: string }): string {
  return (branch.text ?? branch.label ?? '') as string
}

const BRANCH_BASE_MAX_TEXT_WIDTH = 200
const BALANCE_PADDING = 5

function computeBalancedMaxWidth(
  text: string,
  wrapThreshold: number,
  baseCap: number,
  fontSize: number,
  fontWeight = 'normal'
): number {
  if (typeof document === 'undefined') return wrapThreshold
  const tw = measureTextWidth(text, fontSize, { fontWeight })
  if (tw <= wrapThreshold) return wrapThreshold
  const numLines = Math.ceil(tw / baseCap)
  return Math.min(Math.ceil(tw / numLines) + BALANCE_PADDING, baseCap)
}

/**
 * Estimate rendered BranchNode width from text content.
 * Uses DOM-based measureTextWidth for accuracy, with balanced-width
 * approximation matching CSS text-wrap: balance in BranchNode.vue.
 */
function estimateNodeWidth(text: string): number {
  if (!text) return DEFAULT_NODE_WIDTH
  const branchFontSize = 16
  const nodeHorizontalExtra = 38
  const minNodeWidth = 80

  if (typeof document === 'undefined') {
    return Math.max(minNodeWidth, text.length * 9 + nodeHorizontalExtra)
  }

  const fullWidth = measureTextWidth(text, branchFontSize)
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
  let effectiveTextWidth = fullWidth
  if (fullWidth > wrapThreshold) {
    const numLines = Math.ceil(fullWidth / BRANCH_BASE_MAX_TEXT_WIDTH)
    effectiveTextWidth = Math.ceil(fullWidth / numLines) + BALANCE_PADDING
    effectiveTextWidth = Math.min(effectiveTextWidth, BRANCH_BASE_MAX_TEXT_WIDTH)
  }

  return Math.max(minNodeWidth, effectiveTextWidth + nodeHorizontalExtra)
}

const BRANCH_BORDER_Y = 6
const BRANCH_PADDING_Y = 16

/**
 * Measure rendered BranchNode height using DOM measurement.
 * Uses measureTextDimensions with balanced max-width matching BranchNode + InlineEditableText:
 * font 16px normal, text wraps at balanced max-width (CSS text-wrap: balance),
 * then add BranchNode py-2 (16px) and border 3px x 2 (6px). Enforce min-height 36px.
 * For KaTeX labels the rendered DOM height is measured directly.
 */
function measureBranchNodeHeight(text: string): number {
  if (!text) return BRANCH_NODE_HEIGHT
  const branchFontSize = 16
  const wrapThreshold = computeScriptAwareMaxWidth(text, BRANCH_BASE_MAX_TEXT_WIDTH)
  const maxTextWidth = computeBalancedMaxWidth(text, wrapThreshold, BRANCH_BASE_MAX_TEXT_WIDTH, branchFontSize)

  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    const contentH = measureRenderedDiagramLabelHeight(text, branchFontSize, maxTextWidth)
    return Math.max(BRANCH_NODE_HEIGHT, Math.ceil(contentH + BRANCH_PADDING_Y + BRANCH_BORDER_Y))
  }

  const { height: textHeight } = measureTextDimensions(text, branchFontSize, {
    maxWidth: maxTextWidth,
    paddingX: 0,
    paddingY: 0,
  })
  return Math.max(BRANCH_NODE_HEIGHT, textHeight + BRANCH_PADDING_Y + BRANCH_BORDER_Y)
}

const TOPIC_CJK_REGEX =
  /[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]/g

const TOPIC_BASE_MAX_TEXT_WIDTH = 300

/**
 * Estimate rendered TopicNode width from text content.
 * Uses DOM-based measureTextWidth with balanced-width approximation
 * matching CSS text-wrap: balance in TopicNode.vue (cap=300px).
 */
export function estimateTopicNodeWidth(text: string): number {
  if (!text) return DEFAULT_NODE_WIDTH
  const topicFontSize = 18
  const topicPaddingX = 48
  const topicBorderX = 6
  const minTopicWidth = DEFAULT_NODE_WIDTH

  if (typeof document === 'undefined') {
    const cjkMatches = text.match(TOPIC_CJK_REGEX)
    const cjkCount = cjkMatches ? cjkMatches.length : 0
    const otherCount = text.length - cjkCount
    const rawWidth = cjkCount * 19 + otherCount * 11
    return Math.max(minTopicWidth, Math.min(rawWidth, TOPIC_BASE_MAX_TEXT_WIDTH) + topicPaddingX + topicBorderX)
  }

  const fullWidth = measureTextWidth(text, topicFontSize, { fontWeight: 'bold' })
  let effectiveTextWidth = fullWidth
  if (fullWidth > TOPIC_BASE_MAX_TEXT_WIDTH) {
    const numLines = Math.ceil(fullWidth / TOPIC_BASE_MAX_TEXT_WIDTH)
    effectiveTextWidth = Math.ceil(fullWidth / numLines) + BALANCE_PADDING
    effectiveTextWidth = Math.min(effectiveTextWidth, TOPIC_BASE_MAX_TEXT_WIDTH)
  }

  return Math.max(minTopicWidth, effectiveTextWidth + topicPaddingX + topicBorderX)
}

/**
 * Estimate rendered TopicNode height from text content.
 * Uses balanced max-width matching CSS text-wrap: balance in TopicNode.vue.
 * For KaTeX labels the rendered DOM height is measured directly.
 */
export function estimateTopicNodeHeight(text: string): number {
  if (!text) return DEFAULT_NODE_HEIGHT
  const topicFontSize = 18
  const maxTextWidth = computeBalancedMaxWidth(text, TOPIC_BASE_MAX_TEXT_WIDTH, TOPIC_BASE_MAX_TEXT_WIDTH, topicFontSize, 'bold')
  const paddingY = 32
  const borderY = 6

  if (diagramLabelLikelyNeedsRenderedMeasure(text)) {
    const contentH = measureRenderedDiagramLabelHeight(text, topicFontSize, maxTextWidth, {
      fontWeight: 'bold',
    })
    return Math.max(DEFAULT_NODE_HEIGHT, Math.ceil(contentH + paddingY + borderY))
  }

  const { height: textHeight } = measureTextDimensions(text, topicFontSize, {
    fontWeight: 'bold',
    maxWidth: maxTextWidth,
    paddingX: 0,
    paddingY: 0,
  })
  const lineHeight = 27
  const numLines = Math.max(1, Math.ceil(textHeight / lineHeight))
  return Math.max(DEFAULT_NODE_HEIGHT, numLines * lineHeight + paddingY + borderY)
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

  function buildBranch(nodeId: string): MindMapBranch | null {
    const node = nodeMap.get(nodeId)
    if (!node || nodeId === 'topic') return null
    const childIds = childrenMap.get(nodeId) ?? []
    const children = childIds
      .map((id) => buildBranch(id))
      .filter((b): b is MindMapBranch => b !== null)
    return {
      text: node.text ?? '',
      children: children.length > 0 ? children : undefined,
    }
  }

  const topicChildIds = childrenMap.get('topic') ?? []
  // ID format: branch-{side}-{depth}-{globalIndex}; sort by globalIndex to preserve layout order
  const sortByGlobalIndex = (a: string, b: string): number => {
    const aParts = a.split('-')
    const bParts = b.split('-')
    const aIdx = parseInt(aParts[3] ?? '0', 10)
    const bIdx = parseInt(bParts[3] ?? '0', 10)
    return aIdx - bIdx
  }
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
 * Replaces the Dagre-based layout: Y positions are assigned by vertical
 * stacking (bottom-up centering), X positions by a column system keyed on
 * depth (max estimated width per depth level + fixed gap).
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
  _totalBranches: number
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
    const estimatedWidth = estimateNodeWidth(text)
    const estimatedHeight = measureBranchNodeHeight(text)
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
  let totalH = 0
  topLevel.forEach((node, i) => {
    totalH += subtreeHeight(node)
    if (i < topLevel.length - 1) totalH += crossBranchGap
  })

  let currentY = topicCenterY - totalH / 2
  topLevel.forEach((node, i) => {
    if (i > 0) currentY += crossBranchGap
    if (node.children.length === 0) {
      yPos.set(node.id, currentY)
      currentY += node.estimatedHeight
    } else {
      const childEnd = assignChildrenY(node.children, currentY)
      const childrenSpan = childEnd - currentY

      if (childrenSpan >= node.estimatedHeight) {
        const firstChild = node.children[0]
        const lastChild = node.children[node.children.length - 1]
        const childTop = yPos.get(firstChild.id) ?? currentY
        const childBottom = (yPos.get(lastChild.id) ?? currentY) + lastChild.estimatedHeight
        const childCenter = (childTop + childBottom) / 2
        yPos.set(node.id, childCenter - node.estimatedHeight / 2)
        currentY = childEnd
      } else {
        const shift = (node.estimatedHeight - childrenSpan) / 2
        shiftDescendantPositions(node, shift)
        yPos.set(node.id, currentY)
        currentY += node.estimatedHeight
      }
    }
  })

  const maxWidths = new Map<number, number>()
  function collectWidths(node: LayoutNode): void {
    maxWidths.set(node.depth, Math.max(maxWidths.get(node.depth) ?? 0, node.estimatedWidth))
    node.children.forEach((c) => collectWidths(c))
  }
  topLevel.forEach((n) => collectWidths(n))

  const columnEdge = new Map<number, number>()
  const depths = Array.from(maxWidths.keys()).sort((a, b) => a - b)

  if (side === 'right') {
    let x = topicCenterX + topicWidth / 2 + rankSeparation
    for (const d of depths) {
      columnEdge.set(d, x)
      x += (maxWidths.get(d) ?? DEFAULT_NODE_WIDTH) + rankSeparation
    }
  } else {
    let x = topicCenterX - topicWidth / 2 - rankSeparation
    for (const d of depths) {
      columnEdge.set(d, x)
      x -= (maxWidths.get(d) ?? DEFAULT_NODE_WIDTH) + rankSeparation
    }
  }

  function createNodes(node: LayoutNode): void {
    const y = yPos.get(node.id) ?? 0
    const edge = columnEdge.get(node.depth) ?? 0
    const x = side === 'right' ? edge : edge - node.estimatedWidth

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
    node.children.forEach((c) => createNodes(c))
  }
  topLevel.forEach((n) => createNodes(n))

  let handleIndex = 0
  function createConnections(node: LayoutNode, parentId: string): void {
    if (parentId === 'topic') {
      const handleId =
        side === 'right' ? `mindmap-right-${handleIndex}` : `mindmap-left-${handleIndex}`
      const targetHandle = side === 'left' ? 'right-target' : 'left'
      const strokeColor = getMindmapBranchColor(node.branchIndex).border

      connections.push({
        id: `edge-topic-${node.id}`,
        source: 'topic',
        target: node.id,
        sourceHandle: handleId,
        targetHandle,
        style: { strokeColor },
      })
      handleIndex++
    } else {
      const isLeftSide = side === 'left'
      const strokeColor = getMindmapBranchColor(node.branchIndex).border

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
    allBranches.length
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
    allBranches.length
  )

  // Step 3: Center topic node vertically relative to all first-level branches
  let minBranchY = Infinity
  let maxBranchY = -Infinity
  nodes.forEach((node) => {
    if (node.type === 'branch') {
      const isFirstLevel = connections.some(
        (conn) => conn.source === 'topic' && conn.target === node.id
      )
      if (isFirstLevel && node.position) {
        const nodeH = (node.data?.estimatedHeight as number) || DEFAULT_NODE_HEIGHT
        const nodeTop = node.position.y
        const nodeBottom = node.position.y + nodeH
        if (nodeTop < minBranchY) minBranchY = nodeTop
        if (nodeBottom > maxBranchY) maxBranchY = nodeBottom
      }
    }
  })

  if (minBranchY !== Infinity && maxBranchY !== -Infinity && topicNode.position) {
    const branchesCenterY = (minBranchY + maxBranchY) / 2
    topicNode.position.y = branchesCenterY - topicEstimatedHeight / 2
  }

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
