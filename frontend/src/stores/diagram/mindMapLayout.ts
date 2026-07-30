import {
  DEFAULT_CENTER_X,
  DEFAULT_MINDMAP_BRANCH_GAP,
  DEFAULT_MINDMAP_RANK_SEPARATION,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  MINDMAP_SIBLING_GAP,
} from '@/composables/diagrams/layoutConfig'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import {
  mindMapConnectionAnchorY,
  mindMapNodeTopYForAnchorY,
  resolveMindMapTopicLayoutWidth,
} from '@/config/mindMapGeometry'
import type { Connection, DiagramNode } from '@/types'
import { isMindMapConnectorVerboseDebugEnabled } from '@/utils/mindMapConnectorDebugLevel'
import { logMindMapProcess } from '@/utils/mindMapConnectorDebugVerbose'
import {
  markMindMapLoadFirstMeasure,
  markMindMapLoadStage,
  scheduleMindMapLoadSettle,
} from '@/utils/mindMapLoadDebug'
import {
  applyMindMapL1HeightDeltaShift,
  centerMindMapSidePacksOnTopic,
  computeSequentialRootStartYsFrom,
  computeSymmetricRootStartYs,
  settleMindMapPreserveYLayout,
} from '@/utils/mindMapSideStacking'

import type { DiagramContext } from './types'

/**
 * Mind map layout width tracking slice.
 * Manages topic-node and per-node measured widths,
 * triggering reactive column-position recalculation.
 *
 * Batch mode (after loadFromSpec): accumulate unique node measure reports, then
 * one recalc when all expected nodes report (or safety timeout). Value-equal
 * reports still count — seeded estimates often match DOM within 1px.
 */
/** After the last unique measure report, flush without waiting for reused nodes. */
const MEASURE_BATCH_QUIET_MS = 64
/**
 * Fallback when mounts never report. Cancelled on the first unique report so a
 * long main-thread stall cannot leave an overdue timer racing quiet flush.
 */
const MEASURE_BATCH_ARM_SAFETY_MS = 1500
/** Fallback after progress has started but quiet/count0 never completes. */
const MEASURE_BATCH_PROGRESS_SAFETY_MS = 750

export function useMindMapLayoutSlice(ctx: DiagramContext) {
  let measureBatchExpected = 0
  let measureBatchReported: Set<string> | null = null
  let measureBatchSafetyTimer: ReturnType<typeof setTimeout> | null = null
  let measureBatchQuietTimer: ReturnType<typeof setTimeout> | null = null

  function clearMindMapMeasureBatchTimers(): void {
    if (measureBatchSafetyTimer != null) {
      clearTimeout(measureBatchSafetyTimer)
      measureBatchSafetyTimer = null
    }
    if (measureBatchQuietTimer != null) {
      clearTimeout(measureBatchQuietTimer)
      measureBatchQuietTimer = null
    }
  }

  function clearMindMapMeasureBatchSafetyTimer(): void {
    if (measureBatchSafetyTimer != null) {
      clearTimeout(measureBatchSafetyTimer)
      measureBatchSafetyTimer = null
    }
  }

  function armMindMapMeasureBatchSafety(ms: number): void {
    clearMindMapMeasureBatchSafetyTimer()
    measureBatchSafetyTimer = setTimeout(() => {
      measureBatchSafetyTimer = null
      flushMindMapMeasureBatch('timeout')
    }, ms)
  }

  function setBulkLoading(active: boolean): void {
    ctx.mindMapBulkLoading.value = active
  }

  function isMeasureBatchActive(): boolean {
    return measureBatchReported != null && measureBatchExpected > 0
  }

  function flushMindMapMeasureBatch(reason: 'count0' | 'quiet' | 'timeout'): void {
    clearMindMapMeasureBatchTimers()
    if (!isMeasureBatchActive()) {
      setBulkLoading(false)
      return
    }
    const reported = measureBatchReported?.size ?? 0
    measureBatchExpected = 0
    measureBatchReported = null
    setBulkLoading(false)
    markMindMapLoadStage('measure:batch:flush', { reason, reported })
    if (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map') {
      ctx.scheduleMindMapRecalc()
    }
    scheduleMindMapLoadSettle(`batch:${reason}`)
  }

  function armMindMapMeasureBatch(count: number): void {
    clearMindMapMeasureBatchTimers()
    measureBatchExpected = Math.max(0, count)
    if (measureBatchExpected <= 0) {
      measureBatchReported = null
      setBulkLoading(false)
      return
    }
    measureBatchReported = new Set()
    setBulkLoading(true)
    markMindMapLoadStage('measure:batch:arm', { pending: measureBatchExpected })
    // Arm-only safety — replaced by progress safety on the first unique report.
    armMindMapMeasureBatchSafety(MEASURE_BATCH_ARM_SAFETY_MS)
  }

  function scheduleAfterMindMapMeasure(changed: boolean, nodeId?: string): void {
    if (ctx.type.value !== 'mindmap' && ctx.type.value !== 'mind_map') return

    if (isMeasureBatchActive() && measureBatchReported) {
      if (nodeId) {
        const wasNew = !measureBatchReported.has(nodeId)
        measureBatchReported.add(nodeId)
        markMindMapLoadFirstMeasure(nodeId)
        if (measureBatchReported.size >= measureBatchExpected) {
          flushMindMapMeasureBatch('count0')
          return
        }
        // Reused Vue Flow nodes often never re-measure; flush shortly after the
        // last unique report instead of waiting for a full unique set.
        if (wasNew) {
          // Reset progress safety on each unique id so a 750ms-from-first
          // timer cannot flush while unique reports are still streaming in.
          armMindMapMeasureBatchSafety(MEASURE_BATCH_PROGRESS_SAFETY_MS)
          if (measureBatchQuietTimer != null) {
            clearTimeout(measureBatchQuietTimer)
          }
          measureBatchQuietTimer = setTimeout(() => {
            measureBatchQuietTimer = null
            flushMindMapMeasureBatch('quiet')
          }, MEASURE_BATCH_QUIET_MS)
        }
      }
      return
    }

    if (!changed) return
    ctx.scheduleMindMapRecalc()
  }

  function setMindMapTopicWidth(width: number): void {
    const prev = ctx.mindMapTopicActualWidth.value
    if (prev != null && Math.abs(prev - width) < 1) {
      // Still count toward measure-batch even when estimate matches DOM.
      scheduleAfterMindMapMeasure(false, 'topic')
      return
    }
    ctx.mindMapTopicActualWidth.value = width
    scheduleAfterMindMapMeasure(true, 'topic')
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
    scheduleAfterMindMapMeasure(changed, nodeId)
  }

  function setMindMapNodeDimensions(
    nodeId: string,
    width: number | null | undefined,
    height: number | null | undefined
  ): void {
    let changed = false
    let heightDelta: number | null = null

    // null clears; undefined leaves the axis unchanged (e.g. height-only while editing).
    if (width === null) {
      if (nodeId in ctx.mindMapNodeWidths.value) {
        delete ctx.mindMapNodeWidths.value[nodeId]
        changed = true
      }
    } else if (width !== undefined) {
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
    } else if (height !== undefined) {
      const prev = ctx.mindMapNodeHeights.value[nodeId]
      if (prev === undefined || Math.abs(prev - height) >= 1) {
        if (typeof prev === 'number') {
          heightDelta = height - prev
        }
        ctx.mindMapNodeHeights.value[nodeId] = height
        changed = true
      }
    }

    if (
      heightDelta != null &&
      Math.abs(heightDelta) >= 0.5 &&
      ctx.mindMapPreserveIncomingY.value &&
      ctx.data.value?.nodes &&
      ctx.data.value.connections
    ) {
      // Sticky preserve skips full Y restack — push L1 roots below locally.
      ctx.data.value.nodes = applyMindMapL1HeightDeltaShift(
        ctx.data.value.nodes,
        ctx.data.value.connections,
        nodeId,
        heightDelta,
        ctx.mindMapNodeHeights.value
      )
    }

    scheduleAfterMindMapMeasure(changed, nodeId)
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

    // Always notify batch (unique-id settle); recalc only when values changed.
    scheduleAfterMindMapMeasure(changed, 'topic')
  }

  function clearMindMapNodeWidths(): void {
    measureBatchExpected = 0
    measureBatchReported = null
    clearMindMapMeasureBatchTimers()
    setBulkLoading(false)
    ctx.mindMapNodeWidths.value = {}
    ctx.mindMapNodeHeights.value = {}
  }

  return {
    armMindMapMeasureBatch,
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

/** Options for v2 column layout passes. */
export interface MindMapV2LayoutOptions {
  /**
   * Keep every node's incoming Y and only recompute X.
   * Used after incremental L1 Enter so the first paint is already final.
   */
  preserveIncomingY?: boolean
}

/**
 * Recalculate mind-map node positions using subtree-relative X and balanced Y.
 *
 * X: Each node is placed one rankSeparation beyond its parent (not a global depth column).
 * Y: DOM-measured heights re-stack siblings and re-center parents on their children.
 */
/** V2 mind map column layout (underline anchors, sequential side stacking). */
export function recalculateMindMapV2ColumnPositions(
  nodes: DiagramNode[],
  topicWidth: number | null,
  nodeWidths: Record<string, number>,
  nodeHeights: Record<string, number> = {},
  connections: Connection[] = [],
  collapsedNodeIds: ReadonlySet<string> = new Set<string>(),
  diagramStyleId?: string | null,
  options?: MindMapV2LayoutOptions
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
  const effectiveTopicWidth = resolveMindMapTopicLayoutWidth(topicWidth, storedEstimate)
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

  const nodeMap = new Map<string, DiagramNode>()
  for (const n of nodes) nodeMap.set(n.id, n)

  // Left L1 share one outer column (max width on that side). Per-node width made
  // shorter labels jump toward the topic after edit-end measure / canvas click.
  let leftL1ColumnWidth = 0
  for (const rootId of childrenMap.get('topic') ?? []) {
    if (!rootId.startsWith('branch-l-')) continue
    const root = nodeMap.get(rootId)
    if (!root) continue
    leftL1ColumnWidth = Math.max(leftL1ColumnWidth, getNodeWidth(root, nodeWidths))
  }

  const newX = new Map<string, number>()

  function assignSubtreeX(nodeId: string, parentId: string, side: 'r' | 'l'): void {
    const node = nodeMap.get(nodeId)
    if (!node) return
    const w = getNodeWidth(node, nodeWidths)

    let x: number
    if (parentId === 'topic') {
      if (side === 'r') {
        // Right L1: shared inner (left) edge — width does not move X.
        x = topicRightEdge + gap
      } else {
        const colW = leftL1ColumnWidth > 0 ? leftL1ColumnWidth : w
        x = topicLeftEdge - gap - colW
      }
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

  const rightGap = (childrenMap.get('topic') ?? []).some((id) => id.startsWith('branch-r-'))
    ? gap
    : 0
  const leftGap = (childrenMap.get('topic') ?? []).some((id) => id.startsWith('branch-l-'))
    ? gap
    : 0

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
  // Skip full restack when the caller already placed Y (incremental L1 Enter):
  // restacking L1s was the "weird then fixes itself" flash. Still rigid-center
  // each parent↔children group and each side pack on the topic.
  if (connections.length > 0 && !options?.preserveIncomingY) {
    correctedNodes = correctYPositions(
      correctedNodes,
      nodeHeights,
      connections,
      collapsedNodeIds,
      diagramStyleId
    )
  } else if (connections.length > 0 && options?.preserveIncomingY) {
    correctedNodes = settleMindMapPreserveYLayout(
      correctedNodes,
      connections,
      nodeHeights,
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
  const topicChildren = childrenMap.get('topic') ?? []
  if (topicChildren.length === 0) return nodes

  const crossBranchGap = DEFAULT_MINDMAP_BRANCH_GAP

  // First-level branches by side — connection list order is sibling SoT
  const rightRoots: string[] = []
  const leftRoots: string[] = []
  for (const cid of topicChildren) {
    const parsed = parseNodeId(cid)
    if (!parsed) continue
    if (parsed.side === 'r') rightRoots.push(cid)
    else leftRoots.push(cid)
  }

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

    // Sole underline child: align its connection anchor to the parent's so the
    // stem is flat horizontal (underline continues from parent mid; text sits above).
    // Leaves and chains (L1→L2→L3) — box-mid centering left the underline below the
    // parent mid and drew a diagonal (common on right-side single-child chains).
    const soleChildId = kids.length === 1 ? (kids[0] ?? null) : null
    if (
      soleChildId &&
      !collapsedNodeIds.has(nodeId) &&
      isUnderlineMindMapNode(soleChildId, nodeMap, diagramStyleId)
    ) {
      newY.set(nodeId, startY)
      const parentAnchorY = getNodeAnchorY(nodeId, startY, nodeMap, nodeHeights, diagramStyleId)
      const soleChildKids = childrenMap.get(soleChildId)
      const provisionalTop = getNodeTopYForAnchor(
        soleChildId,
        parentAnchorY,
        nodeMap,
        nodeHeights,
        diagramStyleId
      )

      if (!soleChildKids || soleChildKids.length === 0) {
        newY.set(soleChildId, provisionalTop)
        return Math.max(
          startY + h,
          provisionalTop + getNodeHeight(soleChildId, nodeMap, nodeHeights, diagramStyleId)
        )
      }

      // Layout grandchildren, then rigid-shift so the direct child's anchor still
      // matches the parent (fan stays relative; stem stays flat).
      const subtreeEnd = assignSubtreeY(soleChildId, provisionalTop)
      const laidOutTop = newY.get(soleChildId) ?? provisionalTop
      const laidOutAnchor = getNodeAnchorY(
        soleChildId,
        laidOutTop,
        nodeMap,
        nodeHeights,
        diagramStyleId
      )
      const delta = parentAnchorY - laidOutAnchor
      if (Math.abs(delta) >= 0.5) {
        const stack = [soleChildId]
        while (stack.length > 0) {
          const id = stack.pop()
          if (id == null) continue
          const y = newY.get(id)
          if (y != null) newY.set(id, y + delta)
          const nested = childrenMap.get(id)
          if (nested) {
            for (const kid of nested) stack.push(kid)
          }
        }
      }
      return Math.max(startY + h, subtreeEnd + delta)
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
      const firstAnchorY = getNodeAnchorY(
        firstKid,
        firstKidTopY,
        nodeMap,
        nodeHeights,
        diagramStyleId
      )
      const lastAnchorY = getNodeAnchorY(lastKid, lastKidTopY, nodeMap, nodeHeights, diagramStyleId)
      const anchorCenter = (firstAnchorY + lastAnchorY) / 2
      newY.set(
        nodeId,
        getNodeTopYForAnchor(nodeId, anchorCenter, nodeMap, nodeHeights, diagramStyleId)
      )
      return y
    }

    // Parent taller than the fan: stack kids, then rigid-shift so the
    // first/last connection-anchor midpoint matches the parent anchor
    // (box-span mid left underline L2 below the stem).
    newY.set(nodeId, startY)
    const parentAnchorY = getNodeAnchorY(nodeId, startY, nodeMap, nodeHeights, diagramStyleId)
    let y = startY
    for (let i = 0; i < kids.length; i++) {
      if (i > 0) y += MINDMAP_SIBLING_GAP
      y = assignSubtreeY(kids[i], y)
    }
    const firstKid = kids[0]
    const lastKid = kids[kids.length - 1]
    const firstKidTopY = newY.get(firstKid) ?? startY
    const lastKidTopY = newY.get(lastKid) ?? startY
    const firstAnchorY = getNodeAnchorY(
      firstKid,
      firstKidTopY,
      nodeMap,
      nodeHeights,
      diagramStyleId
    )
    const lastAnchorY = getNodeAnchorY(lastKid, lastKidTopY, nodeMap, nodeHeights, diagramStyleId)
    const delta = parentAnchorY - (firstAnchorY + lastAnchorY) / 2
    if (Math.abs(delta) >= 0.5) {
      for (const kidId of kids) {
        shiftSubtreeInNewY(kidId, delta)
      }
    }
    return Math.max(startY + h, y + delta)
  }

  function sidePackOriginTop(roots: string[]): number | undefined {
    const firstRoot = roots[0]
    if (firstRoot == null) return undefined
    // Subtree packing starts at the first child's top when present. The L1 node
    // itself is often re-centered inside a taller child span, so its Y is not
    // a safe pack origin.
    const firstKids = childrenMap.get(firstRoot)
    if (firstKids && firstKids.length > 0 && !collapsedNodeIds.has(firstRoot)) {
      return nodeMap.get(firstKids[0])?.position?.y
    }
    return nodeMap.get(firstRoot)?.position?.y
  }

  function shiftSubtreeInNewY(rootId: string, delta: number): void {
    if (Math.abs(delta) < 0.5) return
    const stack = [rootId]
    while (stack.length > 0) {
      const id = stack.pop()
      if (id == null) continue
      const y = newY.get(id)
      if (y != null) newY.set(id, y + delta)
      const kids = childrenMap.get(id)
      if (kids) {
        for (const kid of kids) stack.push(kid)
      }
    }
  }

  function stackBranches(roots: string[], topicCenterY: number): void {
    if (roots.length === 0) return

    const allPinned = roots.every((rootId) => {
      const y = nodeMap.get(rootId)?.position?.y
      return y != null && Number.isFinite(y)
    })

    // Multi-root with existing tops: keep each L1 where it is (Enter / measure
    // must not re-center the side). Reflow children inside each subtree only.
    if (roots.length >= 2 && allPinned) {
      for (const rootId of roots) {
        const pinY = nodeMap.get(rootId)?.position?.y
        if (pinY == null) continue
        assignSubtreeY(rootId, pinY)
        const laidOutY = newY.get(rootId)
        if (laidOutY == null) continue
        shiftSubtreeInNewY(rootId, pinY - laidOutY)
      }
      return
    }

    const spans = roots.map((r) => computeSubtreeSpan(r))
    const packOrigin = sidePackOriginTop(roots)
    const startYs =
      roots.length >= 2 && packOrigin != null
        ? computeSequentialRootStartYsFrom(packOrigin, spans, crossBranchGap)
        : computeSymmetricRootStartYs(spans, topicCenterY, crossBranchGap)

    for (let i = 0; i < roots.length; i++) {
      assignSubtreeY(roots[i], startYs[i] ?? topicCenterY)
    }
  }

  const topicTopY = nodeMap.get('topic')?.position?.y ?? 0
  const topicCenterY = getNodeAnchorY('topic', topicTopY, nodeMap, nodeHeights, diagramStyleId)

  stackBranches(rightRoots, topicCenterY)
  stackBranches(leftRoots, topicCenterY)

  // Keep topic where it is; each side pack is centered on it below (or already
  // is, when stackBranches used topic-symmetric start Ys).
  newY.set('topic', topicTopY)

  function alignSingleSideRootToTopic(roots: string[]): void {
    if (roots.length !== 1) return
    const rootId = roots[0]
    if (!rootId) return
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

  const yCorrected = nodes.map((node) => {
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

  // Pinned / incremental packs: slide each side as a rigid body onto the topic.
  return centerMindMapSidePacksOnTopic(yCorrected, connections, nodeHeights)
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
