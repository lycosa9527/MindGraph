import {
  DEFAULT_CENTER_X,
  DEFAULT_MINDMAP_BRANCH_GAP,
  DEFAULT_MINDMAP_RANK_SEPARATION,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  MINDMAP_SIBLING_GAP,
} from '@/composables/diagrams/layoutConfig'
import {
  estimateNodeWidth as estimateBranchWidth,
  estimateTopicNodeWidth,
  measureBranchNodeHeight,
  measureBranchNodeUnderlineHeight,
} from '@/stores/specLoader/mindMap'
import { computeSymmetricRootStartYs } from '@/utils/mindMapSideStacking'
import { resolveNodeShape } from '@/utils/nodeShapeStyle'
import { mindMapConnectionAnchorY, mindMapNodeTopYForAnchorY } from '@/config/mindMapGeometry'
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

function getNodeWidth(node: DiagramNode, nodeWidths: Record<string, number>): number {
  const measured = nodeWidths[node.id]
  const freshEstimate = estimateBranchWidth(node.text ?? '')
  const stored = (node.data?.estimatedWidth as number | undefined) ?? DEFAULT_NODE_WIDTH
  const estimated = Math.max(stored, freshEstimate)
  return measured !== undefined ? Math.max(measured, estimated) : estimated
}

function getNodeHeight(
  nodeId: string,
  nodeMap: Map<string, DiagramNode>,
  nodeHeights: Record<string, number>
): number {
  const measured = nodeHeights[nodeId]
  const node = nodeMap.get(nodeId)
  const shape = resolveNodeShape(node?.style, true)
  const measureHeight =
    shape === 'underline' ? measureBranchNodeUnderlineHeight : measureBranchNodeHeight
  const freshEstimate = node?.text ? measureHeight(node.text, nodeId) : DEFAULT_NODE_HEIGHT
  const stored = (node?.data?.estimatedHeight as number | undefined) ?? DEFAULT_NODE_HEIGHT
  const estimated = Math.max(stored, freshEstimate)
  return measured !== undefined ? Math.max(measured, estimated) : estimated
}

function getNodeAnchorY(
  nodeId: string,
  nodeTopY: number,
  nodeMap: Map<string, DiagramNode>,
  nodeHeights: Record<string, number>
): number {
  const node = nodeMap.get(nodeId)
  const h = getNodeHeight(nodeId, nodeMap, nodeHeights)
  const shape = resolveNodeShape(node?.style, true)
  return mindMapConnectionAnchorY(nodeTopY, h, shape)
}

function getNodeTopYForAnchor(
  nodeId: string,
  anchorY: number,
  nodeMap: Map<string, DiagramNode>,
  nodeHeights: Record<string, number>
): number {
  const node = nodeMap.get(nodeId)
  const h = getNodeHeight(nodeId, nodeMap, nodeHeights)
  const shape = resolveNodeShape(node?.style, true)
  return mindMapNodeTopYForAnchorY(anchorY, h, shape)
}

export interface MindMapColumnResult {
  nodes: DiagramNode[]
  gaps: { left: number; right: number }
}

/**
 * Recalculate mind-map node positions using subtree-relative X and balanced Y.
 *
 * X: Each node is placed one rankSeparation beyond its parent (not a global depth column).
 * Y: DOM-measured heights re-stack siblings and re-center parents on their children.
 */
export function recalculateMindMapColumnPositions(
  nodes: DiagramNode[],
  topicWidth: number | null,
  nodeWidths: Record<string, number>,
  nodeHeights: Record<string, number> = {},
  connections: Connection[] = [],
  collapsedNodeIds: ReadonlySet<string> = new Set<string>()
): MindMapColumnResult {
  const topicNode = nodes.find((n) => n.id === 'topic')
  if (!topicNode?.position) return { nodes, gaps: { left: 0, right: 0 } }

  const storedEstimate =
    (topicNode.data?.estimatedWidth as number | undefined) ?? DEFAULT_NODE_WIDTH
  const freshEstimate = estimateTopicNodeWidth(topicNode.text ?? '')
  const bestEstimate = Math.max(storedEstimate, freshEstimate)

  const effectiveTopicWidth =
    topicWidth != null ? Math.max(topicWidth, freshEstimate) : bestEstimate
  const gap = DEFAULT_MINDMAP_RANK_SEPARATION

  const centerX = topicNode.position.x + effectiveTopicWidth / 2
  const topicRightEdge = centerX + effectiveTopicWidth / 2
  const topicLeftEdge = centerX - effectiveTopicWidth / 2

  const childrenMap = new Map<string, string[]>()
  for (const c of connections) {
    const kids = childrenMap.get(c.source)
    if (kids) {
      kids.push(c.target)
    } else {
      childrenMap.set(c.source, [c.target])
    }
  }
  for (const kids of childrenMap.values()) {
    kids.sort((a, b) => {
      const aIdx = parseInt(a.split('-')[3] ?? '0', 10)
      const bIdx = parseInt(b.split('-')[3] ?? '0', 10)
      return aIdx - bIdx
    })
  }

  const nodeMap = new Map<string, DiagramNode>()
  for (const n of nodes) nodeMap.set(n.id, n)

  const newX = new Map<string, number>()

  function assignSubtreeX(nodeId: string, parentId: string, side: 'r' | 'l'): void {
    const node = nodeMap.get(nodeId)
    if (!node) return
    const w = getNodeWidth(node, nodeWidths)

    let x: number
    if (parentId === 'topic') {
      x = side === 'r' ? topicRightEdge + gap : topicLeftEdge - gap - w
    } else {
      const parent = nodeMap.get(parentId)
      if (!parent?.position) return
      const parentW = getNodeWidth(parent, nodeWidths)
      const parentX = newX.get(parentId) ?? parent.position.x
      x = side === 'r' ? parentX + parentW + gap : parentX - gap - w
    }
    newX.set(nodeId, x)

    if (collapsedNodeIds.has(nodeId)) return
    for (const childId of childrenMap.get(nodeId) ?? []) {
      assignSubtreeX(childId, nodeId, side)
    }
  }

  for (const rootId of childrenMap.get('topic') ?? []) {
    const parsed = parseNodeId(rootId)
    if (!parsed) continue
    assignSubtreeX(rootId, 'topic', parsed.side)
  }

  const rightGap =
    (childrenMap.get('topic') ?? []).some((id) => id.startsWith('branch-r-')) ? gap : 0
  const leftGap =
    (childrenMap.get('topic') ?? []).some((id) => id.startsWith('branch-l-')) ? gap : 0

  let correctedNodes = nodes.map((node) => {
    if (!node.position) return node

    if (node.id === 'topic') {
      const newX = centerX - effectiveTopicWidth / 2
      if (Math.abs(node.position.x - newX) < 0.5) return node
      return { ...node, position: { ...node.position, x: newX } }
    }

    const correctedX = newX.get(node.id)
    if (correctedX == null) return node
    if (Math.abs(node.position.x - correctedX) < 0.5) return node
    return { ...node, position: { ...node.position, x: correctedX } }
  })

  // --- Y-position correction using actual measured heights ---
  if (connections.length > 0) {
    correctedNodes = correctYPositions(correctedNodes, nodeHeights, connections, collapsedNodeIds)
  }

  return { nodes: correctedNodes, gaps: { left: leftGap, right: rightGap } }
}

// ---------------------------------------------------------------------------
// Y-position correction: re-stack siblings using DOM-measured heights
// ---------------------------------------------------------------------------

function correctYPositions(
  nodes: DiagramNode[],
  nodeHeights: Record<string, number>,
  connections: Connection[],
  collapsedNodeIds: ReadonlySet<string> = new Set<string>()
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
  for (const kids of childrenMap.values()) {
    kids.sort((a, b) => {
      const aIdx = parseInt(a.split('-')[3] ?? '0', 10)
      const bIdx = parseInt(b.split('-')[3] ?? '0', 10)
      return aIdx - bIdx
    })
  }

  const topicChildren = childrenMap.get('topic') ?? []
  if (topicChildren.length === 0) return nodes

  const crossBranchGap = DEFAULT_MINDMAP_BRANCH_GAP

  // Separate first-level branches by side
  const rightRoots: string[] = []
  const leftRoots: string[] = []
  for (const cid of topicChildren) {
    const parsed = parseNodeId(cid)
    if (!parsed) continue
    if (parsed.side === 'r') rightRoots.push(cid)
    else leftRoots.push(cid)
  }

  // Sort roots by stable global index (not stale Y) so re-stack stays in tree order
  const byGlobalIndex = (a: string, b: string) => {
    const aIdx = parseInt(a.split('-')[3] ?? '0', 10)
    const bIdx = parseInt(b.split('-')[3] ?? '0', 10)
    return aIdx - bIdx
  }
  rightRoots.sort(byGlobalIndex)
  leftRoots.sort(byGlobalIndex)

  const newY = new Map<string, number>()

  function computeSubtreeSpan(nodeId: string): number {
    const h = getNodeHeight(nodeId, nodeMap, nodeHeights)
    if (collapsedNodeIds.has(nodeId)) return h
    const kids = childrenMap.get(nodeId)
    if (!kids || kids.length === 0) return h
    const childSpans = kids.map((kid) => computeSubtreeSpan(kid))
    const childrenTotalSpan =
      childSpans.reduce((a, b) => a + b, 0) + (kids.length - 1) * MINDMAP_SIBLING_GAP
    return Math.max(h, childrenTotalSpan)
  }

  function assignSubtreeY(nodeId: string, startY: number): number {
    const h = getNodeHeight(nodeId, nodeMap, nodeHeights)
    const kids = childrenMap.get(nodeId)

    if (!kids || kids.length === 0 || collapsedNodeIds.has(nodeId)) {
      newY.set(nodeId, startY)
      return startY + h
    }

    const childSpans = kids.map((kid) => computeSubtreeSpan(kid))
    const childrenTotalSpan =
      childSpans.reduce((a, b) => a + b, 0) + (kids.length - 1) * MINDMAP_SIBLING_GAP

    if (childrenTotalSpan >= h) {
      let y = startY
      for (let i = 0; i < kids.length; i++) {
        if (i > 0) y += MINDMAP_SIBLING_GAP
        y = assignSubtreeY(kids[i], y)
      }
      const childTop = newY.get(kids[0]) ?? startY
      const lastKid = kids[kids.length - 1]
      const lastKidH = getNodeHeight(lastKid, nodeMap, nodeHeights)
      const childBottom = (newY.get(lastKid) ?? startY) + lastKidH
      const childCenter = (childTop + childBottom) / 2
      newY.set(nodeId, getNodeTopYForAnchor(nodeId, childCenter, nodeMap, nodeHeights))
      return y
    }

    newY.set(nodeId, startY)
    const shift = (h - childrenTotalSpan) / 2
    let y = startY + shift
    for (let i = 0; i < kids.length; i++) {
      if (i > 0) y += MINDMAP_SIBLING_GAP
      y = assignSubtreeY(kids[i], y)
    }
    return startY + h
  }

  function stackBranches(roots: string[], topicCenterY: number): void {
    if (roots.length === 0) return

    if (roots.length === 2) {
      const spans = roots.map((r) => computeSubtreeSpan(r))
      const startYs = computeSymmetricRootStartYs(spans, topicCenterY, crossBranchGap)
      for (let i = 0; i < roots.length; i++) {
        assignSubtreeY(roots[i], startYs[i] ?? topicCenterY)
      }
      return
    }

    const spans = roots.map((r) => computeSubtreeSpan(r))
    const totalHeight =
      spans.reduce((a, b) => a + b, 0) + Math.max(0, roots.length - 1) * crossBranchGap
    let y = topicCenterY - totalHeight / 2
    for (let i = 0; i < roots.length; i++) {
      y = assignSubtreeY(roots[i], y)
      if (i < roots.length - 1) y += crossBranchGap
    }
  }

  const topicTopY = nodeMap.get('topic')?.position?.y ?? 0
  const topicCenterY = getNodeAnchorY('topic', topicTopY, nodeMap, nodeHeights)

  stackBranches(rightRoots, topicCenterY)
  stackBranches(leftRoots, topicCenterY)

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
