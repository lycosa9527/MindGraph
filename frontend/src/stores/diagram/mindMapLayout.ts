import {
  DEFAULT_CENTER_X,
  DEFAULT_MINDMAP_BRANCH_GAP,
  DEFAULT_MINDMAP_RANK_SEPARATION,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  MINDMAP_SIBLING_GAP,
} from '@/composables/diagrams/layoutConfig'
import { computeSymmetricRootStartYs } from '@/utils/mindMapSideStacking'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { mindMapConnectionAnchorY, mindMapNodeTopYForAnchorY } from '@/config/mindMapGeometry'
import type { Connection, DiagramNode } from '@/types'
import { isMindMapConnectorVerboseDebugEnabled } from '@/utils/mindMapConnectorDebugLevel'
import { logMindMapProcess } from '@/utils/mindMapConnectorDebugVerbose'

import type { DiagramContext } from './types'

/**
 * Mind map layout width tracking slice.
 * Manages topic-node and per-node measured widths,
 * triggering reactive column-position recalculation.
 */
export function useMindMapLayoutSlice(ctx: DiagramContext) {
  function setMindMapTopicWidth(width: number): void {
    const prev = ctx.mindMapTopicActualWidth.value
    if (prev != null && Math.abs(prev - width) < 1) return
    ctx.mindMapTopicActualWidth.value = width
    if (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map') {
      ctx.scheduleMindMapRecalc()
    }
  }

  function setMindMapNodeWidth(nodeId: string, width: number | null): void {
    let changed = false
    if (width === null) {
      if (nodeId in ctx.mindMapNodeWidths.value) {
        delete ctx.mindMapNodeWidths.value[nodeId]
        changed = true
      }
    } else {
      const prev = ctx.mindMapNodeWidths.value[nodeId]
      if (prev === undefined || Math.abs(prev - width) >= 1) {
        ctx.mindMapNodeWidths.value[nodeId] = width
        changed = true
      }
    }
    if (changed && (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map')) {
      ctx.scheduleMindMapRecalc()
    }
  }

  function setMindMapNodeDimensions(
    nodeId: string,
    width: number | null,
    height: number | null
  ): void {
    let changed = false

    if (width === null) {
      if (nodeId in ctx.mindMapNodeWidths.value) {
        delete ctx.mindMapNodeWidths.value[nodeId]
        changed = true
      }
    } else {
      const prev = ctx.mindMapNodeWidths.value[nodeId]
      if (prev === undefined || Math.abs(prev - width) >= 1) {
        ctx.mindMapNodeWidths.value[nodeId] = width
        changed = true
      }
    }

    if (height === null) {
      if (nodeId in ctx.mindMapNodeHeights.value) {
        delete ctx.mindMapNodeHeights.value[nodeId]
        changed = true
      }
    } else {
      const prev = ctx.mindMapNodeHeights.value[nodeId]
      if (prev === undefined || Math.abs(prev - height) >= 1) {
        ctx.mindMapNodeHeights.value[nodeId] = height
        changed = true
      }
    }

    if (changed && (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map')) {
      ctx.scheduleMindMapRecalc()
    }
  }

  function setMindMapTopicMeasured(width: number, height: number): void {
    let changed = false

    const prevW = ctx.mindMapTopicActualWidth.value
    if (prevW === null || Math.abs(prevW - width) >= 1) {
      ctx.mindMapTopicActualWidth.value = width
      changed = true
    }

    const prevH = ctx.mindMapNodeHeights.value.topic
    if (prevH === undefined || Math.abs(prevH - height) >= 1) {
      ctx.mindMapNodeHeights.value.topic = height
      changed = true
    }

    if (changed && (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map')) {
      ctx.scheduleMindMapRecalc()
    }
  }

  function clearMindMapNodeWidths(): void {
    ctx.mindMapNodeWidths.value = {}
    ctx.mindMapNodeHeights.value = {}
  }

  return {
    setMindMapTopicWidth,
    setMindMapTopicMeasured,
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
  if (measured !== undefined) return measured
  return (node.data?.estimatedWidth as number | undefined) ?? DEFAULT_NODE_WIDTH
}

/**
 * Resolve the node's vertical size for layout restack.
 * Prefer Pinia DOM-measured height; otherwise the build-time / text-edit estimate.
 * Never sync-measure text here — `correctYPositions` calls this many times per node
 * and DOM measure would stall the main thread after every branch edit.
 * Shape-correct estimates are written at load / text / style change sites instead.
 */
function getNodeHeight(
  nodeId: string,
  nodeMap: Map<string, DiagramNode>,
  nodeHeights: Record<string, number>,
  _diagramStyleId?: string | null
): number {
  const measured = nodeHeights[nodeId]
  if (measured !== undefined) return measured
  const node = nodeMap.get(nodeId)
  return (node?.data?.estimatedHeight as number | undefined) ?? DEFAULT_NODE_HEIGHT
}

function getNodeAnchorY(
  nodeId: string,
  nodeTopY: number,
  nodeMap: Map<string, DiagramNode>,
  nodeHeights: Record<string, number>,
  diagramStyleId?: string | null
): number {
  const node = nodeMap.get(nodeId)
  const h = getNodeHeight(nodeId, nodeMap, nodeHeights, diagramStyleId)
  const shape = resolveMindMapNodeShape(
    { id: nodeId, type: node?.type ?? 'branch', style: node?.style },
    diagramStyleId
  )
  return mindMapConnectionAnchorY(nodeTopY, h, shape)
}

/** Top-left Y for a node whose connection anchor (underline / center) should sit at anchorY. */
function getNodeTopYForAnchor(
  nodeId: string,
  anchorY: number,
  nodeMap: Map<string, DiagramNode>,
  nodeHeights: Record<string, number>,
  diagramStyleId?: string | null
): number {
  const node = nodeMap.get(nodeId)
  const h = getNodeHeight(nodeId, nodeMap, nodeHeights, diagramStyleId)
  const shape = resolveMindMapNodeShape(
    { id: nodeId, type: node?.type ?? 'branch', style: node?.style },
    diagramStyleId
  )
  return mindMapNodeTopYForAnchorY(anchorY, h, shape)
}

function isUnderlineMindMapNode(
  nodeId: string,
  nodeMap: Map<string, DiagramNode>,
  diagramStyleId?: string | null
): boolean {
  const node = nodeMap.get(nodeId)
  if (!node) return false
  return (
    resolveMindMapNodeShape(
      { id: nodeId, type: node.type ?? 'branch', style: node.style },
      diagramStyleId
    ) === 'underline'
  )
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
/** V2 mind map column layout (underline anchors, symmetric stacking). */
export function recalculateMindMapV2ColumnPositions(
  nodes: DiagramNode[],
  topicWidth: number | null,
  nodeWidths: Record<string, number>,
  nodeHeights: Record<string, number> = {},
  connections: Connection[] = [],
  collapsedNodeIds: ReadonlySet<string> = new Set<string>(),
  diagramStyleId?: string | null
): MindMapColumnResult {
  const topicNode = nodes.find((n) => n.id === 'topic')
  if (!topicNode?.position) return { nodes, gaps: { left: 0, right: 0 } }

  if (isMindMapConnectorVerboseDebugEnabled()) {
    logMindMapProcess('layout:recalc:start', {
      canvasMode: 'v2',
      nodeCount: nodes.length,
      connectionCount: connections.length,
      collapsedCount: collapsedNodeIds.size,
    })
  }

  const storedEstimate =
    (topicNode.data?.estimatedWidth as number | undefined) ?? DEFAULT_NODE_WIDTH
  const measuredTopicWidth = topicWidth ?? 0

  const effectiveTopicWidth =
    measuredTopicWidth > 0 ? Math.max(measuredTopicWidth, storedEstimate) : storedEstimate
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
    correctedNodes = correctYPositions(
      correctedNodes,
      nodeHeights,
      connections,
      collapsedNodeIds,
      diagramStyleId
    )
  }

  if (isMindMapConnectorVerboseDebugEnabled()) {
    logMindMapProcess('layout:recalc:done', {
      canvasMode: 'v2',
      movedYCount: correctedNodes.filter((node) => {
        const prev = nodes.find((item) => item.id === node.id)
        return (
          prev?.position?.y != null &&
          node.position?.y != null &&
          Math.abs(node.position.y - prev.position.y) >= 0.5
        )
      }).length,
    })
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
  collapsedNodeIds: ReadonlySet<string> = new Set<string>(),
  diagramStyleId?: string | null
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
  /** One span per node per restack — assignSubtreeY would otherwise re-walk each subtree. */
  const subtreeSpanCache = new Map<string, number>()

  function computeSubtreeSpan(nodeId: string): number {
    const cached = subtreeSpanCache.get(nodeId)
    if (cached !== undefined) return cached
    const h = getNodeHeight(nodeId, nodeMap, nodeHeights, diagramStyleId)
    if (collapsedNodeIds.has(nodeId)) {
      subtreeSpanCache.set(nodeId, h)
      return h
    }
    const kids = childrenMap.get(nodeId)
    if (!kids || kids.length === 0) {
      subtreeSpanCache.set(nodeId, h)
      return h
    }
    const childSpans = kids.map((kid) => computeSubtreeSpan(kid))
    const childrenTotalSpan =
      childSpans.reduce((a, b) => a + b, 0) + (kids.length - 1) * MINDMAP_SIBLING_GAP
    const span = Math.max(h, childrenTotalSpan)
    subtreeSpanCache.set(nodeId, span)
    return span
  }

  function assignSubtreeY(nodeId: string, startY: number): number {
    const h = getNodeHeight(nodeId, nodeMap, nodeHeights, diagramStyleId)
    const kids = childrenMap.get(nodeId)

    if (!kids || kids.length === 0 || collapsedNodeIds.has(nodeId)) {
      newY.set(nodeId, startY)
      return startY + h
    }

    const childSpans = kids.map((kid) => computeSubtreeSpan(kid))
    const childrenTotalSpan =
      childSpans.reduce((a, b) => a + b, 0) + (kids.length - 1) * MINDMAP_SIBLING_GAP

    // Sole underline leaf: align its underline anchor to the parent's connection anchor
    // so the edge is a flat horizontal (no diagonal when parent is taller than the child).
    const soleChildId = kids.length === 1 ? kids[0]! : null
    const soleChildKids = soleChildId ? childrenMap.get(soleChildId) : undefined
    if (
      soleChildId &&
      !collapsedNodeIds.has(nodeId) &&
      isUnderlineMindMapNode(soleChildId, nodeMap, diagramStyleId) &&
      (!soleChildKids || soleChildKids.length === 0)
    ) {
      newY.set(nodeId, startY)
      const parentAnchorY = getNodeAnchorY(nodeId, startY, nodeMap, nodeHeights, diagramStyleId)
      const childTopY = getNodeTopYForAnchor(
        soleChildId,
        parentAnchorY,
        nodeMap,
        nodeHeights,
        diagramStyleId
      )
      newY.set(soleChildId, childTopY)
      return Math.max(
        startY + h,
        childTopY + getNodeHeight(soleChildId, nodeMap, nodeHeights, diagramStyleId)
      )
    }

    if (childrenTotalSpan >= h) {
      let y = startY
      for (let i = 0; i < kids.length; i++) {
        if (i > 0) y += MINDMAP_SIBLING_GAP
        y = assignSubtreeY(kids[i], y)
      }
      const firstKid = kids[0]
      const lastKid = kids[kids.length - 1]
      const firstKidTopY = newY.get(firstKid) ?? startY
      const lastKidTopY = newY.get(lastKid) ?? startY
      const firstAnchorY = getNodeAnchorY(firstKid, firstKidTopY, nodeMap, nodeHeights, diagramStyleId)
      const lastAnchorY = getNodeAnchorY(lastKid, lastKidTopY, nodeMap, nodeHeights, diagramStyleId)
      const anchorCenter = (firstAnchorY + lastAnchorY) / 2
      newY.set(nodeId, getNodeTopYForAnchor(nodeId, anchorCenter, nodeMap, nodeHeights, diagramStyleId))
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
  const topicCenterY = getNodeAnchorY('topic', topicTopY, nodeMap, nodeHeights, diagramStyleId)

  stackBranches(rightRoots, topicCenterY)
  stackBranches(leftRoots, topicCenterY)

  // Subtree re-centering moves L1 nodes after the initial stack; re-align topic so its
  // connection anchor sits at the midpoint of all L1 branch anchors (both sides).
  const allRoots = [...rightRoots, ...leftRoots]
  if (allRoots.length > 0) {
    let minAnchor = Infinity
    let maxAnchor = -Infinity
    for (const rootId of allRoots) {
      const topY = newY.get(rootId)
      if (topY == null) continue
      const anchor = getNodeAnchorY(rootId, topY, nodeMap, nodeHeights, diagramStyleId)
      minAnchor = Math.min(minAnchor, anchor)
      maxAnchor = Math.max(maxAnchor, anchor)
    }
    if (Number.isFinite(minAnchor) && Number.isFinite(maxAnchor)) {
      const targetAnchorY = (minAnchor + maxAnchor) / 2
      newY.set(
        'topic',
        getNodeTopYForAnchor('topic', targetAnchorY, nodeMap, nodeHeights, diagramStyleId)
      )
    }
  }

  function alignSingleSideRootToTopic(roots: string[]): void {
    if (roots.length !== 1) return
    const rootId = roots[0]
    if (!rootId) return
    const topicTopY = newY.get('topic') ?? nodeMap.get('topic')?.position?.y ?? 0
    const topicAnchorY = getNodeAnchorY('topic', topicTopY, nodeMap, nodeHeights, diagramStyleId)
    newY.set(
      rootId,
      getNodeTopYForAnchor(rootId, topicAnchorY, nodeMap, nodeHeights, diagramStyleId)
    )
  }

  alignSingleSideRootToTopic(rightRoots)
  alignSingleSideRootToTopic(leftRoots)

  if (newY.size === 0) return nodes

  if (isMindMapConnectorVerboseDebugEnabled()) {
    logMindMapProcess('layout:y-correct:start', {
      canvasMode: 'v2',
      nodeCount: nodes.length,
      assignedCount: newY.size,
    })
  }

  return nodes.map((node) => {
    const correctedY = newY.get(node.id)
    if (correctedY == null || !node.position) return node
    if (Math.abs(node.position.y - correctedY) < 0.5) return node
    const prevY = node.position.y
    const shape = resolveMindMapNodeShape(
      { id: node.id, type: node.type ?? 'branch', style: node.style },
      diagramStyleId
    )
    const h = getNodeHeight(node.id, nodeMap, nodeHeights, diagramStyleId)
    if (isMindMapConnectorVerboseDebugEnabled()) {
      logMindMapProcess('layout:y-correct:result', {
        nodeId: node.id,
        shape,
        prevY,
        nextY: correctedY,
        deltaY: correctedY - prevY,
        layoutHeight: h,
        layoutAnchorY: mindMapConnectionAnchorY(correctedY, h, shape),
      })
    }
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
