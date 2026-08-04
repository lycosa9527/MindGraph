/**
 * In-place mind-map sibling insert (v2): mint one id + edge, place Y, shift below.
 * Connection-list order under a parent is the sibling SoT — no full spec reload.
 */
import { BRANCH_NODE_HEIGHT, DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
import {
  mindMapAdaptiveBranchGap,
  mindMapAdaptiveSiblingGap,
} from '@/config/mindMapAdaptiveGaps'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { resolveMindMapTopicBorderColor } from '@/config/mindMapGeometry'
import type { Connection, DiagramNode } from '@/types'
import { MINDMAP_NODE_UID_DATA_KEY, readMindMapNodeUid } from '@/utils/mindMapNodeUid'
import { recordMindMapSiblingInsertFailure } from '@/utils/mindMapSiblingDebug'
import {
  applyMindMapIncrementalTopLevelSiblingLayout,
  settleMindMapPreserveYLayout,
} from '@/utils/mindMapSideStacking'
import type { NodeShape } from '@/utils/nodeShapeStyle'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

import { buildMindMapChildrenMapByConnectionOrder } from './mindMapStylePreservation'

export type InsertMindMapSiblingPosition = 'above' | 'below'

export type InsertMindMapSiblingInPlaceOptions = {
  text: string
  /** Anchor sibling — used when insertIndex / afterNodeId are omitted. */
  anchorNodeId?: string
  position?: InsertMindMapSiblingPosition
  /** Absolute index among parent's children (overrides position / afterNodeId). */
  insertIndex?: number
  /** Insert immediately after this sibling under the same parent. */
  afterNodeId?: string
  /** Required when inserting by index without an anchor (parent of the new node). */
  parentId?: string
  nodeHeights?: Record<string, number>
  nodeWidths?: Record<string, number>
  /** Diagram style — needed so underline L2 anchors match edge routing. */
  diagramStyleId?: string | null
  /** Collapsed nodes — settle must ignore hidden fans (same as layout). */
  collapsedNodeIds?: ReadonlySet<string>
}

export type InsertMindMapSiblingInPlaceResult = {
  nodes: DiagramNode[]
  connections: Connection[]
  newNodeId: string
  newUid: string
  isTopLevel: boolean
  /** Estimated dims to seed measured maps (no DOM yet). */
  estimatedWidth: number
  estimatedHeight: number
}

function parseBranchId(
  nodeId: string
): { side: 'l' | 'r'; depth: number; globalIndex: number } | null {
  const m = /^branch-([lr])-(\d+)-(\d+)$/.exec(nodeId)
  if (!m) return null
  return {
    side: m[1] as 'l' | 'r',
    depth: parseInt(m[2], 10),
    globalIndex: parseInt(m[3], 10),
  }
}

function nextFreeGlobalIndex(nodes: DiagramNode[], side: 'l' | 'r'): number {
  const prefix = `branch-${side}-`
  let max = -1
  for (const node of nodes) {
    if (!node.id.startsWith(prefix)) continue
    const parsed = parseBranchId(node.id)
    if (parsed && parsed.globalIndex > max) max = parsed.globalIndex
  }
  return max + 1
}

function nodeLayoutHeight(node: DiagramNode, heights?: Record<string, number>): number {
  const measured = heights?.[node.id]
  if (typeof measured === 'number' && measured > 0) return measured
  const estimated = node.data?.estimatedHeight
  return typeof estimated === 'number' && estimated > 0 ? estimated : BRANCH_NODE_HEIGHT
}

function nodeLayoutWidth(node: DiagramNode, widths?: Record<string, number>): number {
  const measured = widths?.[node.id]
  if (typeof measured === 'number' && measured > 0) return measured
  const estimated = node.data?.estimatedWidth
  return typeof estimated === 'number' && estimated > 0 ? estimated : DEFAULT_NODE_WIDTH
}

function collectDescendantIds(rootId: string, childrenMap: Map<string, string[]>): string[] {
  const out: string[] = []
  const stack = [...(childrenMap.get(rootId) ?? [])]
  while (stack.length > 0) {
    const id = stack.pop()
    if (id == null) continue
    out.push(id)
    const kids = childrenMap.get(id)
    if (kids) stack.push(...kids)
  }
  return out
}

function subtreeVerticalBounds(
  rootId: string,
  nodeById: Map<string, DiagramNode>,
  childrenMap: Map<string, string[]>,
  heights?: Record<string, number>
): { minY: number; maxY: number } | null {
  const root = nodeById.get(rootId)
  if (!root?.position) return null
  let minY = root.position.y
  let maxY = root.position.y + nodeLayoutHeight(root, heights)
  for (const id of collectDescendantIds(rootId, childrenMap)) {
    const node = nodeById.get(id)
    if (!node?.position) continue
    minY = Math.min(minY, node.position.y)
    maxY = Math.max(maxY, node.position.y + nodeLayoutHeight(node, heights))
  }
  return { minY, maxY }
}

function withShiftedY(node: DiagramNode, delta: number): DiagramNode {
  if (!node.position || Math.abs(delta) < 0.5) return node
  return {
    ...node,
    position: { ...node.position, y: node.position.y + delta },
  }
}

function estimateNewBranchDims(
  anchor: DiagramNode | undefined,
  widths?: Record<string, number>,
  heights?: Record<string, number>
): { width: number; height: number } {
  // Prefer neighbor size so gaps match before first DOM measure.
  const width = anchor ? nodeLayoutWidth(anchor, widths) : DEFAULT_NODE_WIDTH
  const height = anchor ? nodeLayoutHeight(anchor, heights) : BRANCH_NODE_HEIGHT
  return { width, height }
}

/**
 * Sibling ids under a parent for insert/Y SoT.
 * Topic L1: same side only — left/right are separate stacks.
 */
function siblingIdsForInsert(
  connections: Connection[],
  parentId: string,
  side: 'l' | 'r' | null
): string[] {
  const targets = connections.filter((c) => c.source === parentId).map((c) => c.target)
  if (parentId !== 'topic' || side == null) return targets
  const prefix = `branch-${side}-`
  return targets.filter((id) => id.startsWith(prefix))
}

function resolveSideHint(options: InsertMindMapSiblingInPlaceOptions): 'l' | 'r' | null {
  for (const id of [options.anchorNodeId, options.afterNodeId]) {
    if (!id) continue
    const parsed = parseBranchId(id)
    if (parsed) return parsed.side
  }
  if (options.parentId && options.parentId !== 'topic') {
    const parsed = parseBranchId(options.parentId)
    if (parsed) return parsed.side
  }
  // Bare topic insert_index: default right (Kitty side default).
  if (options.parentId === 'topic' || options.insertIndex != null) return 'r'
  return null
}

function resolveInsertContext(
  connections: Connection[],
  options: InsertMindMapSiblingInPlaceOptions
): {
  parentId: string
  /** Index among {@link siblingIdsForInsert} (same-side for topic). */
  insertIndex: number
  anchorNodeId: string | null
  side: 'l' | 'r' | null
} | null {
  const position = options.position ?? 'below'
  const side = resolveSideHint(options)

  if (typeof options.insertIndex === 'number' && options.insertIndex >= 0) {
    const parentId =
      options.parentId ??
      (options.anchorNodeId
        ? connections.find((c) => c.target === options.anchorNodeId)?.source
        : undefined) ??
      (options.afterNodeId
        ? connections.find((c) => c.target === options.afterNodeId)?.source
        : undefined)
    if (!parentId) {
      recordMindMapSiblingInsertFailure('insert_index_missing_parent', {
        insertIndex: options.insertIndex,
        anchorNodeId: options.anchorNodeId,
        afterNodeId: options.afterNodeId,
        parentId: options.parentId,
      })
      return null
    }
    const siblings = siblingIdsForInsert(connections, parentId, side)
    const insertIndex = Math.min(options.insertIndex, siblings.length)
    const anchorNodeId =
      options.anchorNodeId ??
      options.afterNodeId ??
      siblings[Math.max(0, insertIndex - 1)] ??
      siblings[0] ??
      null
    return { parentId, insertIndex, anchorNodeId, side }
  }

  if (options.afterNodeId) {
    const parentId = connections.find((c) => c.target === options.afterNodeId)?.source
    if (!parentId) {
      recordMindMapSiblingInsertFailure('after_node_missing_parent', {
        afterNodeId: options.afterNodeId,
      })
      return null
    }
    const afterSide = parseBranchId(options.afterNodeId)?.side ?? side
    const siblings = siblingIdsForInsert(connections, parentId, afterSide)
    const afterIdx = siblings.indexOf(options.afterNodeId)
    if (afterIdx < 0) {
      recordMindMapSiblingInsertFailure('after_node_not_in_siblings', {
        afterNodeId: options.afterNodeId,
        parentId,
        side: afterSide,
        siblings,
      })
      return null
    }
    return {
      parentId,
      insertIndex: afterIdx + 1,
      anchorNodeId: options.afterNodeId,
      side: afterSide,
    }
  }

  const anchorNodeId = options.anchorNodeId
  if (!anchorNodeId || anchorNodeId === 'topic') {
    recordMindMapSiblingInsertFailure('missing_or_topic_anchor', {
      anchorNodeId,
    })
    return null
  }
  const parentId = connections.find((c) => c.target === anchorNodeId)?.source
  if (!parentId) {
    recordMindMapSiblingInsertFailure('anchor_missing_parent_edge', {
      anchorNodeId,
      connectionTargets: connections.map((c) => c.target),
      hint: 'Stale selection after library reload renumbered mind-map ids',
    })
    return null
  }
  const anchorSide = parseBranchId(anchorNodeId)?.side ?? side
  const siblings = siblingIdsForInsert(connections, parentId, anchorSide)
  const anchorIdx = siblings.indexOf(anchorNodeId)
  if (anchorIdx < 0) {
    recordMindMapSiblingInsertFailure('anchor_not_in_side_siblings', {
      anchorNodeId,
      parentId,
      side: anchorSide,
      siblings,
      allChildren: connections.filter((c) => c.source === parentId).map((c) => c.target),
    })
    return null
  }
  const insertIndex = position === 'above' ? anchorIdx : anchorIdx + 1
  return { parentId, insertIndex, anchorNodeId, side: anchorSide }
}

function buildNewConnection(
  parentId: string,
  newNodeId: string,
  side: 'l' | 'r',
  strokeColor: string
): Connection {
  if (parentId === 'topic') {
    return {
      id: `edge-topic-${newNodeId}`,
      source: 'topic',
      target: newNodeId,
      sourceHandle: side === 'r' ? 'mindmap-right' : 'mindmap-left',
      targetHandle: side === 'l' ? 'right-target' : 'left',
      style: { strokeColor },
    }
  }
  const isLeft = side === 'l'
  return {
    id: `edge-${parentId}-${newNodeId}`,
    source: parentId,
    target: newNodeId,
    sourceHandle: isLeft ? 'left-source' : 'right',
    targetHandle: isLeft ? 'right-target' : 'left',
    style: { strokeColor },
  }
}

function spliceParentConnections(
  connections: Connection[],
  parentId: string,
  newConn: Connection,
  insertIndex: number,
  side: 'l' | 'r' | null
): Connection[] {
  // Topic: splice within one side only so left/right stacks stay independent.
  if (parentId === 'topic' && side != null) {
    const prefix = `branch-${side}-`
    const sideConns = connections.filter((c) => c.source === 'topic' && c.target.startsWith(prefix))
    const nextSide = sideConns.slice()
    nextSide.splice(insertIndex, 0, newConn)

    const result: Connection[] = []
    let sideEmitted = false
    for (const conn of connections) {
      if (conn.source === 'topic' && conn.target.startsWith(prefix)) {
        if (!sideEmitted) {
          result.push(...nextSide)
          sideEmitted = true
        }
        continue
      }
      result.push(conn)
    }
    if (!sideEmitted) {
      if (side === 'r') {
        const firstTopic = result.findIndex((c) => c.source === 'topic')
        if (firstTopic < 0) result.push(...nextSide)
        else result.splice(firstTopic, 0, ...nextSide)
      } else {
        let lastTopic = -1
        for (let i = 0; i < result.length; i++) {
          if (result[i]?.source === 'topic') lastTopic = i
        }
        if (lastTopic < 0) result.push(...nextSide)
        else result.splice(lastTopic + 1, 0, ...nextSide)
      }
    }
    return result
  }

  const siblingConns = connections.filter((c) => c.source === parentId)
  const nextSiblings = siblingConns.slice()
  nextSiblings.splice(insertIndex, 0, newConn)

  const result: Connection[] = []
  let siblingsEmitted = false
  for (const conn of connections) {
    if (conn.source === parentId) {
      if (!siblingsEmitted) {
        result.push(...nextSiblings)
        siblingsEmitted = true
      }
      continue
    }
    result.push(conn)
  }
  if (!siblingsEmitted) {
    result.push(...nextSiblings)
  }
  return result
}

function shapeOfNode(
  node: DiagramNode | undefined,
  diagramStyleId?: string | null
): NodeShape {
  if (!node) return 'rounded'
  return resolveMindMapNodeShape(
    { id: node.id, type: node.type ?? 'branch', style: node.style },
    diagramStyleId
  )
}

function applyInPlaceYLayout(
  nodes: DiagramNode[],
  connections: Connection[],
  options: {
    newNodeId: string
    parentId: string
    isTopLevel: boolean
    side: 'l' | 'r' | null
    heights?: Record<string, number>
    diagramStyleId?: string | null
  }
): DiagramNode[] {
  const childrenMap = buildMindMapChildrenMapByConnectionOrder(connections)
  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  const newNode = nodeById.get(options.newNodeId)
  if (!newNode?.position) return nodes

  const newShape = shapeOfNode(newNode, options.diagramStyleId)
  const gapFor = (neighborId: string, neighborIsUpper: boolean): number => {
    const neighbor = nodeById.get(neighborId)
    const neighborShape = shapeOfNode(neighbor, options.diagramStyleId)
    const upper = neighborIsUpper ? neighborShape : newShape
    const lower = neighborIsUpper ? newShape : neighborShape
    return options.isTopLevel
      ? mindMapAdaptiveBranchGap(upper, lower)
      : mindMapAdaptiveSiblingGap(upper, lower)
  }
  const newH = nodeLayoutHeight(newNode, options.heights)
  // L1: only same-side roots participate in vertical stack / shift.
  const siblings = siblingIdsForInsert(
    connections,
    options.parentId,
    options.isTopLevel ? options.side : null
  )
  const newIdx = siblings.indexOf(options.newNodeId)
  if (newIdx < 0) return nodes

  const prevId = newIdx > 0 ? siblings[newIdx - 1] : null
  const nextId = newIdx < siblings.length - 1 ? siblings[newIdx + 1] : null

  let placedY = newNode.position.y
  let shiftDelta = 0

  if (prevId) {
    const prevBounds = subtreeVerticalBounds(prevId, nodeById, childrenMap, options.heights)
    if (prevBounds) {
      const gap = gapFor(prevId, true)
      placedY = prevBounds.maxY + gap
      shiftDelta = newH + gap
    }
  } else if (nextId) {
    // Insert at start: occupy next's top and push next (and below) down.
    const nextBounds = subtreeVerticalBounds(nextId, nodeById, childrenMap, options.heights)
    if (nextBounds) {
      const gap = gapFor(nextId, false)
      placedY = nextBounds.minY
      shiftDelta = newH + gap
    }
  } else {
    const topic = nodeById.get('topic')
    placedY = topic?.position?.y ?? newNode.position.y
  }

  const idsToShift = new Set<string>()
  if (shiftDelta !== 0) {
    for (let i = newIdx + 1; i < siblings.length; i++) {
      const sid = siblings[i]
      idsToShift.add(sid)
      for (const id of collectDescendantIds(sid, childrenMap)) {
        idsToShift.add(id)
      }
    }
  }

  return nodes.map((node) => {
    if (node.id === options.newNodeId && node.position) {
      return { ...node, position: { ...node.position, y: placedY } }
    }
    if (idsToShift.has(node.id)) return withShiftedY(node, shiftDelta)
    return node
  })
}

/**
 * Pure in-place sibling insert. Does not touch Pinia / history.
 */
export function insertMindMapSiblingInPlace(
  nodes: DiagramNode[],
  connections: Connection[],
  options: InsertMindMapSiblingInPlaceOptions
): InsertMindMapSiblingInPlaceResult | null {
  const ctx = resolveInsertContext(connections, options)
  if (!ctx) return null

  const { parentId, insertIndex, anchorNodeId } = ctx
  const existingSiblings = siblingIdsForInsert(connections, parentId, ctx.side)
  const layoutSiblingId =
    (anchorNodeId && existingSiblings.includes(anchorNodeId) ? anchorNodeId : null) ??
    options.afterNodeId ??
    existingSiblings[Math.max(0, insertIndex - 1)] ??
    existingSiblings[0] ??
    null

  const sideHintId = layoutSiblingId ?? (parentId !== 'topic' ? parentId : null)
  if (!sideHintId && parentId !== 'topic' && ctx.side == null) {
    return recordMindMapSiblingInsertFailure('no_side_hint', {
      parentId,
      anchorNodeId,
      layoutSiblingId,
      side: ctx.side,
    })
  }

  // Depth follows the parent link (Enter = same-level sibling below selection):
  // topic child → L1, L1 child → L2, L2 child → L3, …
  // Do not copy depth from a sibling id — stale ids can disagree with the tree.
  let side: 'l' | 'r'
  let depth: number
  if (parentId === 'topic') {
    const parsedSibling = layoutSiblingId ? parseBranchId(layoutSiblingId) : null
    side = parsedSibling?.side ?? ctx.side ?? 'r'
    depth = 1
  } else {
    const parsedParent = parseBranchId(parentId)
    if (!parsedParent) {
      return recordMindMapSiblingInsertFailure('parent_id_unparsed', {
        parentId,
        anchorNodeId,
      })
    }
    side = parsedParent.side
    depth = parsedParent.depth + 1
  }

  const freeIdx = nextFreeGlobalIndex(nodes, side)
  const newNodeId = `branch-${side}-${depth}-${freeIdx}`
  if (nodes.some((n) => n.id === newNodeId)) {
    return recordMindMapSiblingInsertFailure('id_collision', {
      newNodeId,
      freeIdx,
      side,
      depth,
      existingIds: nodes.map((n) => n.id).filter((id) => id.startsWith(`branch-${side}-`)),
    })
  }

  const layoutSibling = layoutSiblingId ? nodes.find((n) => n.id === layoutSiblingId) : undefined
  const { width: estimatedWidth, height: estimatedHeight } = estimateNewBranchDims(
    layoutSibling,
    options.nodeWidths,
    options.nodeHeights
  )

  const topic = nodes.find((n) => n.id === 'topic')
  const strokeColor = resolveMindMapTopicBorderColor(topic)
  const newUid = safeRandomUUID()

  let x = layoutSibling?.position?.x ?? topic?.position?.x ?? 0
  if (layoutSibling?.position && side === 'l') {
    const siblingW = nodeLayoutWidth(layoutSibling, options.nodeWidths)
    x = layoutSibling.position.x + siblingW - estimatedWidth
  } else if (!layoutSibling?.position && topic?.position) {
    x =
      side === 'r'
        ? topic.position.x + nodeLayoutWidth(topic, options.nodeWidths) + 40
        : topic.position.x - estimatedWidth - 40
  }

  const branchIndex =
    typeof layoutSibling?.data?.branchIndex === 'number'
      ? layoutSibling.data.branchIndex
      : insertIndex

  const newNode: DiagramNode = {
    id: newNodeId,
    text: options.text,
    type: 'branch',
    position: {
      x,
      y: layoutSibling?.position?.y ?? topic?.position?.y ?? 0,
    },
    data: {
      branchIndex,
      estimatedWidth,
      estimatedHeight,
      [MINDMAP_NODE_UID_DATA_KEY]: newUid,
    },
  }

  const newConn = buildNewConnection(parentId, newNodeId, side, strokeColor)
  const nextConnections = spliceParentConnections(connections, parentId, newConn, insertIndex, side)

  const isTopLevel = parentId === 'topic'
  let nextNodes: DiagramNode[]

  if (isTopLevel) {
    // Reuse the proven same-side spatial place/shift (not connection-index Y).
    const anchorForLayout = anchorNodeId ?? layoutSiblingId
    const insertDir = resolveTopLevelInsertDirection(
      options,
      insertIndex,
      existingSiblings,
      anchorForLayout
    )
    const beforeNodes = nodes.map((node) => {
      if (!anchorForLayout || node.id !== anchorForLayout) return node
      if (readMindMapNodeUid(node)) return node
      return {
        ...node,
        data: {
          ...node.data,
          [MINDMAP_NODE_UID_DATA_KEY]: safeRandomUUID(),
        },
      }
    })
    const anchorUid =
      (anchorForLayout
        ? readMindMapNodeUid(beforeNodes.find((n) => n.id === anchorForLayout))
        : null) ?? newUid
    const topicY = topic?.position?.y ?? 0
    nextNodes = applyMindMapIncrementalTopLevelSiblingLayout(
      beforeNodes,
      [...beforeNodes, newNode],
      nextConnections,
      {
        anchorUid,
        newSiblingUid: newUid,
        insert: insertDir,
        topicY,
        nodeHeights: options.nodeHeights,
        diagramStyleId: options.diagramStyleId,
      }
    )
  } else {
    nextNodes = applyInPlaceYLayout([...nodes, newNode], nextConnections, {
      newNodeId,
      parentId,
      isTopLevel: false,
      side,
      heights: options.nodeHeights,
      diagramStyleId: options.diagramStyleId,
    })
    // First paint: center fans + separate overlapping sibling packs.
    nextNodes = settleMindMapPreserveYLayout(
      nextNodes,
      nextConnections,
      options.nodeHeights,
      options.collapsedNodeIds ?? new Set<string>(),
      options.diagramStyleId
    )
  }

  return {
    nodes: nextNodes,
    connections: nextConnections,
    newNodeId,
    newUid,
    isTopLevel,
    estimatedWidth,
    estimatedHeight,
  }
}

function resolveTopLevelInsertDirection(
  options: InsertMindMapSiblingInPlaceOptions,
  insertIndex: number,
  existingSiblings: string[],
  anchorNodeId: string | null
): InsertMindMapSiblingPosition {
  if (options.afterNodeId) return 'below'
  if (options.position === 'above' || options.position === 'below') {
    return options.position
  }
  if (anchorNodeId) {
    const anchorIdx = existingSiblings.indexOf(anchorNodeId)
    if (anchorIdx >= 0 && insertIndex <= anchorIdx) return 'above'
  }
  return 'below'
}
