/**
 * Vertical stacking helpers for first-level mind-map branches on one side.
 * Multi-root sides pack sequentially with a uniform cross-branch gap (no n=2
 * special case — that inflated gaps when subtree spans differed).
 *
 * Incremental L1 Enter uses UID position restore + insert/shift so the map
 * grows like L2 (nodes below move) instead of re-centering the whole side.
 */
import {
  DEFAULT_MINDMAP_BRANCH_GAP,
  DEFAULT_NODE_HEIGHT,
  MINDMAP_SIBLING_GAP,
} from '@/composables/diagrams/layoutConfig'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { mindMapConnectionAnchorY } from '@/config/mindMapGeometry'
import type { Connection, DiagramNode } from '@/types'
import { findNodeIdByMindMapUid, readMindMapNodeUid } from '@/utils/mindMapNodeUid'

/** Topic-centered sequential start tops for one side's root subtrees. */
export function computeSymmetricRootStartYs(
  subtreeSpans: number[],
  topicCenterY: number,
  crossBranchGap: number
): number[] {
  const n = subtreeSpans.length
  if (n === 0) return []

  if (n === 1) {
    return [topicCenterY - subtreeSpans[0] / 2]
  }

  const totalHeight = subtreeSpans.reduce((a, b) => a + b, 0) + (n - 1) * crossBranchGap
  let y = topicCenterY - totalHeight / 2
  return subtreeSpans.map((span) => {
    const start = y
    y += span + crossBranchGap
    return start
  })
}

/** Sequential start tops beginning at a fixed first-root top Y. */
export function computeSequentialRootStartYsFrom(
  startY: number,
  subtreeSpans: number[],
  crossBranchGap: number
): number[] {
  let y = startY
  return subtreeSpans.map((span) => {
    const start = y
    y += span + crossBranchGap
    return start
  })
}

/**
 * Translate every node on the anchor's side so the anchor keeps `anchorY`.
 * Used after sibling insert reload so Enter-below does not slide the selected branch.
 */
export function applyMindMapSideAnchorYPreserve(
  nodes: DiagramNode[],
  anchorUid: string,
  anchorY: number
): DiagramNode[] {
  const trimmedUid = anchorUid.trim()
  if (!trimmedUid) return nodes

  const anchor = nodes.find((node) => readMindMapNodeUid(node) === trimmedUid)
  if (!anchor?.position) return nodes

  const sidePrefix = anchor.id.startsWith('branch-l-')
    ? 'branch-l-'
    : anchor.id.startsWith('branch-r-')
      ? 'branch-r-'
      : null
  if (!sidePrefix) return nodes

  const delta = anchorY - anchor.position.y
  if (Math.abs(delta) < 0.5) return nodes

  return nodes.map((node) => {
    if (!node.position || !node.id.startsWith(sidePrefix)) return node
    return {
      ...node,
      position: { ...node.position, y: node.position.y + delta },
    }
  })
}

/** Keep the topic at its pre-insert top Y after a full spec reload. */
export function applyMindMapTopicYPreserve(nodes: DiagramNode[], topicY: number): DiagramNode[] {
  if (!Number.isFinite(topicY)) return nodes

  return nodes.map((node) => {
    if (node.id !== 'topic' || !node.position) return node
    if (Math.abs(node.position.y - topicY) < 0.5) return node
    return {
      ...node,
      position: { ...node.position, y: topicY },
    }
  })
}

function nodeHeightForLayout(node: DiagramNode, nodeHeights?: Record<string, number>): number {
  const measured = nodeHeights?.[node.id]
  if (typeof measured === 'number' && measured > 0) return measured
  return nodeLayoutHeight(node)
}

/**
 * Rigid-translate one side so its L1 connection-anchor midpoint lines up with
 * the topic anchor. Relative gaps from Enter stay intact (whole pack slides).
 * Same SoT as sole-root topic align / edge routing (box mid is wrong for
 * underline L1).
 */
export function centerMindMapSidePackOnTopic(
  nodes: DiagramNode[],
  connections: Connection[],
  side: 'l' | 'r',
  nodeHeights?: Record<string, number>,
  diagramStyleId?: string | null
): DiagramNode[] {
  const topic = nodes.find((node) => node.id === 'topic')
  if (!topic?.position) return nodes

  const sidePrefix = side === 'l' ? 'branch-l-' : 'branch-r-'
  const l1Ids = connections
    .filter((conn) => conn.source === 'topic' && conn.target.startsWith(`${sidePrefix}1-`))
    .map((conn) => conn.target)
  if (l1Ids.length === 0) return nodes

  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  let minAnchor = Infinity
  let maxAnchor = -Infinity
  for (const id of l1Ids) {
    const node = nodeById.get(id)
    if (!node?.position) continue
    const anchor = nodeConnectionAnchorY(node, nodeHeights, diagramStyleId)
    if (anchor == null) continue
    minAnchor = Math.min(minAnchor, anchor)
    maxAnchor = Math.max(maxAnchor, anchor)
  }
  if (!Number.isFinite(minAnchor) || !Number.isFinite(maxAnchor)) return nodes

  const topicAnchor = nodeConnectionAnchorY(topic, nodeHeights, diagramStyleId)
  if (topicAnchor == null) return nodes
  const sideMid = (minAnchor + maxAnchor) / 2
  const delta = topicAnchor - sideMid
  if (Math.abs(delta) < 0.5) return nodes

  return nodes.map((node) => {
    if (!node.position || !node.id.startsWith(sidePrefix)) return node
    return withShiftedY(node, delta)
  })
}

/** Center left and right packs independently on the topic (classic mind-map balance). */
export function centerMindMapSidePacksOnTopic(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeHeights?: Record<string, number>,
  diagramStyleId?: string | null
): DiagramNode[] {
  const left = centerMindMapSidePackOnTopic(
    nodes,
    connections,
    'l',
    nodeHeights,
    diagramStyleId
  )
  return centerMindMapSidePackOnTopic(left, connections, 'r', nodeHeights, diagramStyleId)
}

/**
 * Rigid-translate each non-topic parent's descendant fan so the direct-child
 * group's connection-anchor midpoint matches the parent anchor (same SoT as
 * edge routing / assignSubtreeY — box midpoints are wrong for underline L2).
 * Sibling gaps stay intact. Topic↔L1 balance is side-pack centering.
 */
export function centerMindMapChildrenGroupsOnParents(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeHeights?: Record<string, number>,
  collapsedNodeIds: ReadonlySet<string> = new Set<string>(),
  diagramStyleId?: string | null
): DiagramNode[] {
  const childrenMap = buildChildrenMap(connections)
  const parentIds = [...childrenMap.keys()].filter((id) => id !== 'topic')
  if (parentIds.length === 0) return nodes

  // Deepest first: nested groups settle before an outer slide moves them.
  parentIds.sort((a, b) => branchDepth(b) - branchDepth(a))

  let result = nodes
  for (const parentId of parentIds) {
    if (collapsedNodeIds.has(parentId)) continue
    result = centerOneParentChildrenGroup(
      result,
      parentId,
      childrenMap,
      nodeHeights,
      diagramStyleId
    )
  }
  return result
}

/**
 * Preserve-path Y settle: center each fan on its parent, push overlapping sibling
 * packs apart, repeat once (re-center can expand a fan into a neighbor), then
 * balance each side on the topic.
 */
export function settleMindMapPreserveYLayout(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeHeights?: Record<string, number>,
  collapsedNodeIds: ReadonlySet<string> = new Set<string>(),
  diagramStyleId?: string | null
): DiagramNode[] {
  let result = nodes
  for (let pass = 0; pass < 2; pass++) {
    result = centerMindMapChildrenGroupsOnParents(
      result,
      connections,
      nodeHeights,
      collapsedNodeIds,
      diagramStyleId
    )
    result = resolveMindMapSiblingSubtreeOverlaps(
      result,
      connections,
      nodeHeights,
      collapsedNodeIds
    )
  }
  return centerMindMapSidePacksOnTopic(
    result,
    connections,
    nodeHeights,
    diagramStyleId
  )
}

/**
 * Push sibling subtrees apart when their vertical bounds collide (or gap is too
 * small). Used after children-on-parent centering under sticky preserve — L1
 * Enter pins root tops, so growing child fans would otherwise overlap.
 * Same-side L1 roots use {@link DEFAULT_MINDMAP_BRANCH_GAP}; deeper siblings use
 * {@link MINDMAP_SIBLING_GAP}. Each shifted root moves rigidly with descendants.
 */
export function resolveMindMapSiblingSubtreeOverlaps(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeHeights?: Record<string, number>,
  collapsedNodeIds: ReadonlySet<string> = new Set<string>()
): DiagramNode[] {
  const childrenMap = buildChildrenMap(connections)
  let result = nodes

  // Deeper packs first, then L1 sides (fans may grow after inner pushes + re-center).
  const parents = [...childrenMap.keys()]
    .filter((id) => id !== 'topic' && !collapsedNodeIds.has(id))
    .sort((a, b) => branchDepth(b) - branchDepth(a))

  for (const parentId of parents) {
    const kids = (childrenMap.get(parentId) ?? []).filter((id) => !collapsedNodeIds.has(id))
    if (kids.length < 2) continue
    result = resolveSiblingListOverlaps(result, kids, MINDMAP_SIBLING_GAP, childrenMap, nodeHeights)
  }

  const topicKids = childrenMap.get('topic') ?? []
  const leftL1 = topicKids.filter((id) => id.startsWith('branch-l-1-'))
  const rightL1 = topicKids.filter((id) => id.startsWith('branch-r-1-'))
  result = resolveSiblingListOverlaps(
    result,
    leftL1,
    DEFAULT_MINDMAP_BRANCH_GAP,
    childrenMap,
    nodeHeights
  )
  result = resolveSiblingListOverlaps(
    result,
    rightL1,
    DEFAULT_MINDMAP_BRANCH_GAP,
    childrenMap,
    nodeHeights
  )
  return result
}

/**
 * @deprecated Prefer {@link centerMindMapSidePacksOnTopic} — moving only the topic
 * leaves uneven side packs visually off-center.
 */
export function recenterMindMapTopicToL1Midpoint(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeHeights?: Record<string, number>
): DiagramNode[] {
  return centerMindMapSidePacksOnTopic(nodes, connections, nodeHeights)
}

function nodeLayoutHeight(node: DiagramNode): number {
  const estimated = node.data?.estimatedHeight
  return typeof estimated === 'number' && estimated > 0 ? estimated : DEFAULT_NODE_HEIGHT
}

function isTopLevelBranchId(id: string): boolean {
  return /^branch-[lr]-1-/.test(id)
}

function branchDepth(id: string): number {
  const match = /^branch-[lr]-(\d+)-/.exec(id)
  if (!match) return 0
  return Number.parseInt(match[1], 10)
}

function sidePrefixForBranchId(id: string): 'branch-l-' | 'branch-r-' | null {
  if (id.startsWith('branch-l-')) return 'branch-l-'
  if (id.startsWith('branch-r-')) return 'branch-r-'
  return null
}

function nodeConnectionAnchorY(
  node: DiagramNode,
  nodeHeights?: Record<string, number>,
  diagramStyleId?: string | null
): number | null {
  if (!node.position) return null
  const height = nodeHeightForLayout(node, nodeHeights)
  const shape = resolveMindMapNodeShape(
    { id: node.id, type: node.type ?? 'branch', style: node.style },
    diagramStyleId
  )
  return mindMapConnectionAnchorY(node.position.y, height, shape)
}

function centerOneParentChildrenGroup(
  nodes: DiagramNode[],
  parentId: string,
  childrenMap: Map<string, string[]>,
  nodeHeights?: Record<string, number>,
  diagramStyleId?: string | null
): DiagramNode[] {
  const kids = childrenMap.get(parentId)
  if (!kids || kids.length === 0) return nodes

  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const parent = nodeById.get(parentId)
  if (!parent?.position) return nodes

  const parentAnchor = nodeConnectionAnchorY(parent, nodeHeights, diagramStyleId)
  if (parentAnchor == null) return nodes

  let minAnchor = Infinity
  let maxAnchor = -Infinity
  for (const kidId of kids) {
    const kid = nodeById.get(kidId)
    if (!kid) continue
    const anchor = nodeConnectionAnchorY(kid, nodeHeights, diagramStyleId)
    if (anchor == null) continue
    minAnchor = Math.min(minAnchor, anchor)
    maxAnchor = Math.max(maxAnchor, anchor)
  }
  if (!Number.isFinite(minAnchor) || !Number.isFinite(maxAnchor)) return nodes

  const delta = parentAnchor - (minAnchor + maxAnchor) / 2
  if (Math.abs(delta) < 0.5) return nodes

  const shiftIds = new Set(collectDescendantIds(parentId, childrenMap))
  return nodes.map((node) => {
    if (!shiftIds.has(node.id)) return node
    return withShiftedY(node, delta)
  })
}

function buildChildrenMap(connections: Connection[]): Map<string, string[]> {
  const map = new Map<string, string[]>()
  for (const connection of connections) {
    const kids = map.get(connection.source)
    if (kids) kids.push(connection.target)
    else map.set(connection.source, [connection.target])
  }
  return map
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
  nodeHeights?: Record<string, number>
): { minY: number; maxY: number } | null {
  const root = nodeById.get(rootId)
  if (!root?.position) return null
  let minY = root.position.y
  let maxY = root.position.y + nodeHeightForLayout(root, nodeHeights)
  for (const id of collectDescendantIds(rootId, childrenMap)) {
    const node = nodeById.get(id)
    if (!node?.position) continue
    minY = Math.min(minY, node.position.y)
    maxY = Math.max(maxY, node.position.y + nodeHeightForLayout(node, nodeHeights))
  }
  return { minY, maxY }
}

/**
 * Sort siblings by current top Y and push each next subtree down until the
 * required gap below the previous subtree's bottom edge is satisfied.
 */
function resolveSiblingListOverlaps(
  nodes: DiagramNode[],
  siblingIds: string[],
  gap: number,
  childrenMap: Map<string, string[]>,
  nodeHeights?: Record<string, number>
): DiagramNode[] {
  if (siblingIds.length < 2) return nodes

  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const ordered = [...siblingIds].sort((a, b) => {
    const ay = nodeById.get(a)?.position?.y ?? 0
    const by = nodeById.get(b)?.position?.y ?? 0
    return ay - by
  })

  let result = nodes
  for (let i = 1; i < ordered.length; i++) {
    const prevId = ordered[i - 1]
    const currId = ordered[i]
    if (prevId === undefined || currId === undefined) continue
    const byId = new Map(result.map((node) => [node.id, node]))
    const prevBounds = subtreeVerticalBounds(prevId, byId, childrenMap, nodeHeights)
    const currBounds = subtreeVerticalBounds(currId, byId, childrenMap, nodeHeights)
    if (!prevBounds || !currBounds) continue

    const minTop = prevBounds.maxY + gap
    const delta = minTop - currBounds.minY
    if (delta < 0.5) continue

    const shiftIds = new Set<string>([currId, ...collectDescendantIds(currId, childrenMap)])
    result = result.map((node) => (shiftIds.has(node.id) ? withShiftedY(node, delta) : node))
  }
  return result
}

function withShiftedY(node: DiagramNode, delta: number): DiagramNode {
  if (!node.position || Math.abs(delta) < 0.5) return node
  return {
    ...node,
    position: { ...node.position, y: node.position.y + delta },
  }
}

/**
 * After L1 sibling reload: restore prior UID positions, place the new L1, and
 * shift only same-side roots that sit on the insert side of the anchor.
 */
export function applyMindMapIncrementalTopLevelSiblingLayout(
  beforeNodes: DiagramNode[],
  afterNodes: DiagramNode[],
  connections: Connection[],
  options: {
    anchorUid: string
    newSiblingUid: string
    insert: 'above' | 'below'
    topicY: number
    crossBranchGap?: number
    nodeHeights?: Record<string, number>
  }
): DiagramNode[] {
  const gap = options.crossBranchGap ?? DEFAULT_MINDMAP_BRANCH_GAP
  const beforeByUid = new Map<string, { x: number; y: number }>()
  for (const node of beforeNodes) {
    if (!node.position) continue
    const uid = readMindMapNodeUid(node)
    if (uid) beforeByUid.set(uid, { x: node.position.x, y: node.position.y })
  }

  let nodes = afterNodes.map((node) => {
    if (!node.position) return node
    if (node.id === 'topic') {
      if (Math.abs(node.position.y - options.topicY) < 0.5) return node
      return { ...node, position: { ...node.position, y: options.topicY } }
    }
    const uid = readMindMapNodeUid(node)
    if (!uid) return node
    const prev = beforeByUid.get(uid)
    if (!prev) return node
    if (Math.abs(node.position.x - prev.x) < 0.5 && Math.abs(node.position.y - prev.y) < 0.5) {
      return node
    }
    return { ...node, position: { x: prev.x, y: prev.y } }
  })

  const anchorId = findNodeIdByMindMapUid(nodes, options.anchorUid)
  const newId = findNodeIdByMindMapUid(nodes, options.newSiblingUid)
  if (!anchorId || !newId) return nodes

  const sidePrefix = sidePrefixForBranchId(anchorId)
  if (!sidePrefix) return nodes

  const childrenMap = buildChildrenMap(connections)
  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const anchorBounds = subtreeVerticalBounds(anchorId, nodeById, childrenMap, options.nodeHeights)
  const newNode = nodeById.get(newId)
  if (!anchorBounds || !newNode?.position) return nodes

  const newH = nodeLayoutHeight(newNode)
  const placedY =
    options.insert === 'below' ? anchorBounds.maxY + gap : anchorBounds.minY - gap - newH

  const anchor = nodeById.get(anchorId)
  const anchorY = anchor?.position?.y
  if (anchorY == null) return nodes

  const shiftDelta = options.insert === 'below' ? newH + gap : -(newH + gap)
  const idsToShift = new Set<string>()
  for (const node of nodes) {
    if (!node.id.startsWith(sidePrefix) || !isTopLevelBranchId(node.id)) continue
    if (node.id === anchorId || node.id === newId) continue
    if (!node.position) continue
    const shouldShift =
      options.insert === 'below' ? node.position.y > anchorY + 0.5 : node.position.y < anchorY - 0.5
    if (!shouldShift) continue
    idsToShift.add(node.id)
    for (const id of collectDescendantIds(node.id, childrenMap)) {
      idsToShift.add(id)
    }
  }

  nodes = nodes.map((node) => {
    if (node.id === newId && node.position) {
      return { ...node, position: { ...node.position, y: placedY } }
    }
    if (idsToShift.has(node.id)) return withShiftedY(node, shiftDelta)
    return node
  })

  // Keep Enter gaps; slide each side pack so it centers on the topic.
  return centerMindMapSidePacksOnTopic(nodes, connections, options.nodeHeights)
}

/**
 * Under sticky L1 preserve (no full Y restack): when one L1 root's measured
 * height changes, push same-side L1 roots below it (and their subtrees) by the
 * delta. Keeps Enter gaps correct when the new label wraps taller.
 */
export function applyMindMapL1HeightDeltaShift(
  nodes: DiagramNode[],
  connections: Connection[],
  changedL1Id: string,
  heightDelta: number,
  nodeHeights?: Record<string, number>
): DiagramNode[] {
  if (Math.abs(heightDelta) < 0.5) return nodes
  if (!isTopLevelBranchId(changedL1Id)) return nodes

  const changed = nodes.find((node) => node.id === changedL1Id)
  if (!changed?.position) return nodes

  const sidePrefix = sidePrefixForBranchId(changedL1Id)
  if (!sidePrefix) return nodes

  const childrenMap = buildChildrenMap(connections)
  const anchorY = changed.position.y
  const idsToShift = new Set<string>()

  for (const node of nodes) {
    if (!node.id.startsWith(sidePrefix) || !isTopLevelBranchId(node.id)) continue
    if (node.id === changedL1Id || !node.position) continue
    if (node.position.y <= anchorY + 0.5) continue
    idsToShift.add(node.id)
    for (const id of collectDescendantIds(node.id, childrenMap)) {
      idsToShift.add(id)
    }
  }

  const shifted =
    idsToShift.size === 0
      ? nodes
      : nodes.map((node) => (idsToShift.has(node.id) ? withShiftedY(node, heightDelta) : node))
  return centerMindMapSidePacksOnTopic(shifted, connections, nodeHeights)
}

/**
 * L2+ sibling Enter: translate the side so the edited branch keeps its Y.
 * L1 Enter should use {@link applyMindMapIncrementalTopLevelSiblingLayout}.
 */
export function applyMindMapIncrementalSiblingYPreserve(
  nodes: DiagramNode[],
  options: { anchorUid: string; anchorY: number; topicY?: number }
): DiagramNode[] {
  let next = applyMindMapSideAnchorYPreserve(nodes, options.anchorUid, options.anchorY)
  if (options.topicY != null && Number.isFinite(options.topicY)) {
    next = applyMindMapTopicYPreserve(next, options.topicY)
  }
  return next
}

const MIN_DELETE_UID_COVERAGE = 0.5

/**
 * After delete + loadMindMapSpec: restore survivor positions by UID, close the
 * vertical gap left by deleted roots, then settle. Returns ``usedIncremental:
 * false`` when UID coverage is too low (caller should full-recalc).
 */
export function applyMindMapIncrementalDeleteLayout(
  beforeNodes: DiagramNode[],
  beforeConnections: Connection[],
  afterNodes: DiagramNode[],
  afterConnections: Connection[],
  options: {
    deletedNodeIds: string[]
    topicY?: number
    nodeHeights?: Record<string, number>
    collapsedNodeIds?: ReadonlySet<string>
    diagramStyleId?: string | null
  }
): { nodes: DiagramNode[]; usedIncremental: boolean } {
  const survivors = afterNodes.filter(
    (node) => node.id !== 'topic' && node.id.startsWith('branch-')
  )
  if (survivors.length > 0) {
    const withUid = survivors.filter((node) => Boolean(readMindMapNodeUid(node)))
    if (withUid.length / survivors.length < MIN_DELETE_UID_COVERAGE) {
      return { nodes: afterNodes, usedIncremental: false }
    }
  }

  const beforeByUid = new Map<string, { x: number; y: number }>()
  const heightByUid = new Map<string, number>()
  for (const node of beforeNodes) {
    const uid = readMindMapNodeUid(node)
    if (!uid) continue
    if (node.position) {
      beforeByUid.set(uid, { x: node.position.x, y: node.position.y })
    }
    const measured = options.nodeHeights?.[node.id]
    if (typeof measured === 'number' && measured > 0) {
      heightByUid.set(uid, measured)
    }
  }

  let nodes = afterNodes.map((node) => {
    if (!node.position) return node
    if (node.id === 'topic') {
      if (options.topicY == null || !Number.isFinite(options.topicY)) return node
      if (Math.abs(node.position.y - options.topicY) < 0.5) return node
      return { ...node, position: { ...node.position, y: options.topicY } }
    }
    const uid = readMindMapNodeUid(node)
    if (!uid) return node
    const prev = beforeByUid.get(uid)
    if (!prev) return node
    if (
      Math.abs(node.position.x - prev.x) < 0.5
      && Math.abs(node.position.y - prev.y) < 0.5
    ) {
      return node
    }
    return { ...node, position: { x: prev.x, y: prev.y } }
  })

  const afterHeights: Record<string, number> = {}
  for (const node of nodes) {
    const uid = readMindMapNodeUid(node)
    if (!uid) continue
    const h = heightByUid.get(uid)
    if (typeof h === 'number' && h > 0) {
      afterHeights[node.id] = h
    }
  }
  const heightsForLayout = { ...options.nodeHeights, ...afterHeights }

  const beforeChildren = buildChildrenMap(beforeConnections)
  const beforeById = new Map(beforeNodes.map((node) => [node.id, node]))
  const deletedRoots = collectDeletedSubtreeRoots(options.deletedNodeIds, beforeChildren)

  for (const deletedId of deletedRoots) {
    const bounds = subtreeVerticalBounds(
      deletedId,
      beforeById,
      beforeChildren,
      options.nodeHeights
    )
    const deletedNode = beforeById.get(deletedId)
    if (!bounds || !deletedNode?.position) continue

    const gap = isTopLevelBranchId(deletedId)
      ? DEFAULT_MINDMAP_BRANCH_GAP
      : MINDMAP_SIBLING_GAP
    const shift = -(bounds.maxY - bounds.minY + gap)
    if (Math.abs(shift) < 0.5) continue

    const parentId =
      beforeConnections.find((connection) => connection.target === deletedId)?.source ?? 'topic'
    const siblings = beforeChildren.get(parentId) ?? []
    const deletedY = deletedNode.position.y
    const afterChildren = buildChildrenMap(afterConnections)
    const shiftIds = new Set<string>()

    for (const sibId of siblings) {
      if (sibId === deletedId) continue
      const sib = beforeById.get(sibId)
      if (!sib?.position || sib.position.y <= deletedY + 0.5) continue
      const uid = readMindMapNodeUid(sib)
      if (!uid) continue
      const afterSibId = findNodeIdByMindMapUid(nodes, uid)
      if (!afterSibId) continue
      shiftIds.add(afterSibId)
      for (const desc of collectDescendantIds(afterSibId, afterChildren)) {
        shiftIds.add(desc)
      }
    }

    if (shiftIds.size === 0) continue
    nodes = nodes.map((node) => (shiftIds.has(node.id) ? withShiftedY(node, shift) : node))
  }

  nodes = settleMindMapPreserveYLayout(
    nodes,
    afterConnections,
    heightsForLayout,
    options.collapsedNodeIds ?? new Set<string>(),
    options.diagramStyleId
  )
  return { nodes, usedIncremental: true }
}

function collectDeletedSubtreeRoots(
  deletedNodeIds: string[],
  beforeChildren: Map<string, string[]>
): string[] {
  const deletedSet = new Set(
    deletedNodeIds.filter((id) => typeof id === 'string' && id.startsWith('branch-'))
  )
  if (deletedSet.size === 0) return []

  const allRemoved = new Set(deletedSet)
  for (const id of deletedSet) {
    for (const desc of collectDescendantIds(id, beforeChildren)) {
      allRemoved.add(desc)
    }
  }

  const parentOf = new Map<string, string>()
  for (const [parentId, kids] of beforeChildren) {
    for (const kid of kids) {
      parentOf.set(kid, parentId)
    }
  }

  const roots = [...deletedSet].filter((id) => {
    const parentId = parentOf.get(id)
    return !parentId || !allRemoved.has(parentId)
  })

  roots.sort((a, b) => {
    const depthDelta = branchDepth(b) - branchDepth(a)
    if (depthDelta !== 0) return depthDelta
    return a.localeCompare(b)
  })
  return roots
}
