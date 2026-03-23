import {
  DEFAULT_CENTER_X,
  DEFAULT_MINDMAP_RANK_SEPARATION,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_VERTICAL_SPACING,
} from '@/composables/diagrams/layoutConfig'
import type { Connection, DiagramNode } from '@/types'

import type { DiagramContext } from './types'

/**
 * Mind map layout width tracking slice.
 * Manages topic-node and per-node measured widths,
 * triggering reactive column-position recalculation.
 */
export function useMindMapLayoutSlice(ctx: DiagramContext) {
  function setMindMapTopicWidth(width: number): void {
    ctx.mindMapTopicActualWidth.value = width
    if (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map') {
      ctx.mindMapRecalcTrigger.value++
    }
  }

  function setMindMapNodeWidth(nodeId: string, width: number | null): void {
    if (width === null) {
      delete ctx.mindMapNodeWidths.value[nodeId]
    } else {
      ctx.mindMapNodeWidths.value[nodeId] = width
    }
    if (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map') {
      ctx.mindMapRecalcTrigger.value++
    }
  }

  function setMindMapNodeDimensions(
    nodeId: string,
    width: number | null,
    height: number | null
  ): void {
    if (width === null) {
      delete ctx.mindMapNodeWidths.value[nodeId]
    } else {
      ctx.mindMapNodeWidths.value[nodeId] = width
    }
    if (height === null) {
      delete ctx.mindMapNodeHeights.value[nodeId]
    } else {
      ctx.mindMapNodeHeights.value[nodeId] = height
    }
    if (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map') {
      ctx.mindMapRecalcTrigger.value++
    }
  }

  function clearMindMapNodeWidths(): void {
    ctx.mindMapNodeWidths.value = {}
    ctx.mindMapNodeHeights.value = {}
  }

  return {
    setMindMapTopicWidth,
    setMindMapNodeWidth,
    setMindMapNodeDimensions,
    clearMindMapNodeWidths,
  }
}

// ---------------------------------------------------------------------------
// Pure helper: recalculate X positions from measured widths
// ---------------------------------------------------------------------------

interface ParsedNodeId {
  side: 'r' | 'l'
  depth: number
}

function parseNodeId(id: string): ParsedNodeId | null {
  const m = id.match(/^branch-(r|l)-(\d+)-/)
  if (!m) return null
  return { side: m[1] as 'r' | 'l', depth: parseInt(m[2], 10) }
}

function getNodeWidth(
  node: DiagramNode,
  nodeWidths: Record<string, number>
): number {
  return (
    nodeWidths[node.id] ??
    (node.data?.estimatedWidth as number | undefined) ??
    DEFAULT_NODE_WIDTH
  )
}

function getNodeHeight(
  nodeId: string,
  nodeMap: Map<string, DiagramNode>,
  nodeHeights: Record<string, number>
): number {
  return (
    nodeHeights[nodeId] ??
    (nodeMap.get(nodeId)?.data?.estimatedHeight as number | undefined) ??
    DEFAULT_NODE_HEIGHT
  )
}

export interface MindMapColumnResult {
  nodes: DiagramNode[]
  gaps: { left: number; right: number }
}

/**
 * Recalculate mind-map node positions using a column system (X) and
 * DOM-measured heights (Y).
 *
 * X: Each depth level on each side forms a "column". Column X positions chain
 * outward from the topic center with a fixed gap.
 *
 * Y: When actual DOM-measured heights are available, re-stack siblings and
 * re-center parents on their children so that curves stay straight even when
 * text wraps to more lines than estimated.
 */
export function recalculateMindMapColumnPositions(
  nodes: DiagramNode[],
  topicWidth: number | null,
  nodeWidths: Record<string, number>,
  nodeHeights: Record<string, number> = {},
  connections: Connection[] = []
): MindMapColumnResult {
  const topicNode = nodes.find((n) => n.id === 'topic')
  if (!topicNode?.position) return { nodes, gaps: { left: 0, right: 0 } }

  const estimatedTopicWidth =
    (topicNode.data?.estimatedWidth as number | undefined) ?? DEFAULT_NODE_WIDTH

  const effectiveTopicWidth = topicWidth ?? estimatedTopicWidth
  const gap = DEFAULT_MINDMAP_RANK_SEPARATION

  const centerX = topicNode.position.x + estimatedTopicWidth / 2

  // Group branch nodes by side and depth, collecting their widths
  const rightMaxWidths = new Map<number, number>()
  const leftMaxWidths = new Map<number, number>()

  for (const node of nodes) {
    const parsed = parseNodeId(node.id)
    if (!parsed) continue
    const w = getNodeWidth(node, nodeWidths)
    const map = parsed.side === 'r' ? rightMaxWidths : leftMaxWidths
    map.set(parsed.depth, Math.max(map.get(parsed.depth) ?? 0, w))
  }

  const topicRightEdge = centerX + effectiveTopicWidth / 2
  const topicLeftEdge = centerX - effectiveTopicWidth / 2

  // Compute column left-edge positions for right side (chaining outward)
  const rightColumnLeftEdge = new Map<number, number>()
  const rightDepths = Array.from(rightMaxWidths.keys()).sort((a, b) => a - b)
  let rightX = topicRightEdge + gap
  for (const depth of rightDepths) {
    rightColumnLeftEdge.set(depth, rightX)
    rightX += (rightMaxWidths.get(depth) ?? DEFAULT_NODE_WIDTH) + gap
  }

  // Compute column right-edge positions for left side (chaining outward)
  const leftColumnRightEdge = new Map<number, number>()
  const leftDepths = Array.from(leftMaxWidths.keys()).sort((a, b) => a - b)
  let leftX = topicLeftEdge - gap
  for (const depth of leftDepths) {
    leftColumnRightEdge.set(depth, leftX)
    leftX -= (leftMaxWidths.get(depth) ?? DEFAULT_NODE_WIDTH) + gap
  }

  // Measure topic-to-branch gaps (depth-1 column edge to topic edge)
  const rightGap =
    rightDepths.length > 0
      ? (rightColumnLeftEdge.get(rightDepths[0]) ?? topicRightEdge) - topicRightEdge
      : 0
  const leftGap =
    leftDepths.length > 0
      ? topicLeftEdge - (leftColumnRightEdge.get(leftDepths[0]) ?? topicLeftEdge)
      : 0

  // Apply corrected X positions
  let correctedNodes = nodes.map((node) => {
    if (!node.position) return node

    if (node.id === 'topic') {
      const newX = centerX - effectiveTopicWidth / 2
      if (Math.abs(node.position.x - newX) < 0.5) return node
      return { ...node, position: { ...node.position, x: newX } }
    }

    const parsed = parseNodeId(node.id)
    if (!parsed) return node

    const w = getNodeWidth(node, nodeWidths)

    if (parsed.side === 'r') {
      const colLeft = rightColumnLeftEdge.get(parsed.depth)
      if (colLeft == null) return node
      if (Math.abs(node.position.x - colLeft) < 0.5) return node
      return { ...node, position: { ...node.position, x: colLeft } }
    }

    const colRight = leftColumnRightEdge.get(parsed.depth)
    if (colRight == null) return node
    const newX = colRight - w
    if (Math.abs(node.position.x - newX) < 0.5) return node
    return { ...node, position: { ...node.position, x: newX } }
  })

  // --- Y-position correction using actual measured heights ---
  if (connections.length > 0) {
    correctedNodes = correctYPositions(correctedNodes, nodeHeights, connections)
  }

  return { nodes: correctedNodes, gaps: { left: leftGap, right: rightGap } }
}

// ---------------------------------------------------------------------------
// Y-position correction: re-stack siblings using DOM-measured heights
// ---------------------------------------------------------------------------

function correctYPositions(
  nodes: DiagramNode[],
  nodeHeights: Record<string, number>,
  connections: Connection[]
): DiagramNode[] {
  const nodeMap = new Map<string, DiagramNode>()
  for (const n of nodes) nodeMap.set(n.id, n)

  const childrenMap = new Map<string, string[]>()
  for (const c of connections) {
    const kids = childrenMap.get(c.source)
    if (kids) {
      kids.push(c.target)
    } else {
      childrenMap.set(c.source, [c.target])
    }
  }

  const topicChildren = childrenMap.get('topic') ?? []
  if (topicChildren.length === 0) return nodes

  const verticalSpacing = DEFAULT_VERTICAL_SPACING
  const crossBranchGap = verticalSpacing * 1.5

  // Separate first-level branches by side
  const rightRoots: string[] = []
  const leftRoots: string[] = []
  for (const cid of topicChildren) {
    const parsed = parseNodeId(cid)
    if (!parsed) continue
    if (parsed.side === 'r') rightRoots.push(cid)
    else leftRoots.push(cid)
  }

  // Sort roots by their current Y to preserve order
  const byCurrentY = (a: string, b: string) => {
    const ay = nodeMap.get(a)?.position?.y ?? 0
    const by = nodeMap.get(b)?.position?.y ?? 0
    return ay - by
  }
  rightRoots.sort(byCurrentY)
  leftRoots.sort(byCurrentY)

  const newY = new Map<string, number>()

  function computeSubtreeSpan(nodeId: string): number {
    const h = getNodeHeight(nodeId, nodeMap, nodeHeights)
    const kids = childrenMap.get(nodeId)
    if (!kids || kids.length === 0) return h
    const childSpans = kids.map((kid) => computeSubtreeSpan(kid))
    const childrenTotalSpan =
      childSpans.reduce((a, b) => a + b, 0) +
      (kids.length - 1) * verticalSpacing
    return Math.max(h, childrenTotalSpan)
  }

  function assignSubtreeY(nodeId: string, startY: number): number {
    const h = getNodeHeight(nodeId, nodeMap, nodeHeights)
    const kids = childrenMap.get(nodeId)

    if (!kids || kids.length === 0) {
      newY.set(nodeId, startY)
      return startY + h
    }

    const childSpans = kids.map((kid) => computeSubtreeSpan(kid))
    const childrenTotalSpan =
      childSpans.reduce((a, b) => a + b, 0) +
      (kids.length - 1) * verticalSpacing

    if (childrenTotalSpan >= h) {
      let y = startY
      for (let i = 0; i < kids.length; i++) {
        if (i > 0) y += verticalSpacing
        y = assignSubtreeY(kids[i], y)
      }
      const childTop = newY.get(kids[0]) ?? startY
      const lastKid = kids[kids.length - 1]
      const lastKidH = getNodeHeight(lastKid, nodeMap, nodeHeights)
      const childBottom = (newY.get(lastKid) ?? startY) + lastKidH
      const childCenter = (childTop + childBottom) / 2
      newY.set(nodeId, childCenter - h / 2)
      return y
    }

    newY.set(nodeId, startY)
    const shift = (h - childrenTotalSpan) / 2
    let y = startY + shift
    for (let i = 0; i < kids.length; i++) {
      if (i > 0) y += verticalSpacing
      y = assignSubtreeY(kids[i], y)
    }
    return startY + h
  }

  function stackBranches(roots: string[]): void {
    if (roots.length === 0) return
    const spans = roots.map((r) => computeSubtreeSpan(r))
    const totalSpan =
      spans.reduce((a, b) => a + b, 0) +
      (roots.length - 1) * crossBranchGap

    const firstRootY = nodeMap.get(roots[0])?.position?.y ?? 0
    const lastRoot = roots[roots.length - 1]
    const lastRootH = getNodeHeight(lastRoot, nodeMap, nodeHeights)
    const lastRootY = nodeMap.get(lastRoot)?.position?.y ?? 0
    const currentCenter = (firstRootY + lastRootY + lastRootH) / 2

    let startY = currentCenter - totalSpan / 2
    for (let i = 0; i < roots.length; i++) {
      if (i > 0) startY += crossBranchGap
      startY = assignSubtreeY(roots[i], startY)
    }
  }

  stackBranches(rightRoots)
  stackBranches(leftRoots)

  // Re-center topic on all first-level branches
  if (newY.size > 0) {
    let minBranchY = Infinity
    let maxBranchBottom = -Infinity
    for (const cid of topicChildren) {
      const y = newY.get(cid)
      if (y == null) continue
      const h = getNodeHeight(cid, nodeMap, nodeHeights)
      minBranchY = Math.min(minBranchY, y)
      maxBranchBottom = Math.max(maxBranchBottom, y + h)
    }
    if (minBranchY !== Infinity) {
      const branchesCenter = (minBranchY + maxBranchBottom) / 2
      const topicH = DEFAULT_NODE_HEIGHT
      newY.set('topic', branchesCenter - topicH / 2)
    }
  }

  if (newY.size === 0) return nodes

  return nodes.map((node) => {
    const correctedY = newY.get(node.id)
    if (correctedY == null || !node.position) return node
    if (Math.abs(node.position.y - correctedY) < 0.5) return node
    return { ...node, position: { ...node.position, y: correctedY } }
  })
}

/**
 * Derive canvas center X from the current topic node.
 * Falls back to DEFAULT_CENTER_X when the topic position is unknown.
 */
export function getMindMapCenterX(nodes: DiagramNode[]): number {
  const topic = nodes.find((n) => n.id === 'topic')
  if (!topic?.position) return DEFAULT_CENTER_X
  const w = (topic.data?.estimatedWidth as number) || DEFAULT_NODE_WIDTH
  return topic.position.x + w / 2
}
