import type { Connection, DiagramData, DiagramNode } from '@/types'
import {
  findNodeIdByMindMapUid,
  readMindMapNodeUid,
} from '@/utils/mindMapNodeUid'

import {
  findNodeIdByPathKey,
  mindMapNodePathKey,
  sortMindMapNodeIdsByGlobalIndex,
} from './mindMapStylePreservation'

function getMindMapTextSegments(
  nodeId: string,
  nodes: DiagramNode[],
  connections: Connection[]
): string[] | null {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  const parentOf = new Map<string, string>()
  connections.forEach((c) => parentOf.set(c.target, c.source))

  const segments: string[] = []
  let current: string | undefined = nodeId
  while (current && current !== 'topic') {
    const node = nodeMap.get(current)
    if (!node) return null
    segments.unshift(node.text ?? '')
    current = parentOf.get(current)
  }
  return segments.length > 0 ? segments : null
}

function findNodeIdByTextSegments(
  segments: string[],
  nodes: DiagramNode[],
  connections: Connection[],
  parentId: string
): string | null {
  if (segments.length === 0) return null

  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  const childIds = connections
    .filter((c) => c.source === parentId)
    .map((c) => c.target)
    .slice()
    .sort(sortMindMapNodeIdsByGlobalIndex)

  for (const childId of childIds) {
    if ((nodeMap.get(childId)?.text ?? '') !== segments[0]) continue
    if (segments.length === 1) return childId
    const found = findNodeIdByTextSegments(segments.slice(1), nodes, connections, childId)
    if (found) return found
  }
  return null
}

function findNodeIdByTextSegmentsOnSide(
  segments: string[],
  side: 'l' | 'r',
  nodes: DiagramNode[],
  connections: Connection[]
): string | null {
  const prefix = side === 'l' ? 'branch-l-' : 'branch-r-'
  const rootIds = connections
    .filter((c) => c.source === 'topic' && c.target.startsWith(prefix))
    .map((c) => c.target)
    .slice()
    .sort(sortMindMapNodeIdsByGlobalIndex)

  for (const rootId of rootIds) {
    const rootText = nodes.find((n) => n.id === rootId)?.text ?? ''
    if (rootText !== segments[0]) continue
    if (segments.length === 1) return rootId
    const found = findNodeIdByTextSegments(segments.slice(1), nodes, connections, rootId)
    if (found) return found
  }
  return null
}

function textSegmentsEqual(a: string[] | null, b: string[] | null): boolean {
  if (!a || !b || a.length !== b.length) return false
  return a.every((segment, index) => segment === b[index])
}

function directChildTexts(
  nodeId: string,
  nodes: DiagramNode[],
  connections: Connection[]
): string[] {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  return connections
    .filter((c) => c.source === nodeId)
    .map((c) => c.target)
    .slice()
    .sort(sortMindMapNodeIdsByGlobalIndex)
    .map((id) => nodeMap.get(id)?.text ?? '')
}

/**
 * When a branch is reparented, the topic→node text path changes, so path/segment
 * matching fails. Fall back to unique own-text (+ direct-child texts) identity.
 */
function findNodeIdByOwnTextIdentity(
  oldId: string,
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[]
): string | null {
  const oldNode = oldNodes.find((n) => n.id === oldId)
  if (!oldNode) return null
  const ownText = oldNode.text ?? ''
  const oldChildTexts = directChildTexts(oldId, oldNodes, oldConnections)

  const candidates = newNodes.filter(
    (n) => n.id.startsWith('branch-') && (n.text ?? '') === ownText
  )
  if (candidates.length === 0) return null
  if (candidates.length === 1) return candidates[0].id

  const withSameChildren = candidates.filter((n) => {
    const childTexts = directChildTexts(n.id, newNodes, newConnections)
    return (
      childTexts.length === oldChildTexts.length &&
      childTexts.every((text, index) => text === oldChildTexts[index])
    )
  })
  if (withSameChildren.length === 1) return withSameChildren[0].id
  return null
}

/**
 * Resolve a node id across a mind-map tree rebuild.
 * Prefer stable mindMapUid (survives duplicate labels + reparent).
 * Then path key when text identity still matches; else text path / own-text fallback.
 */
export function remapMindMapNodeIdAfterReload(
  oldId: string,
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[]
): string | null {
  if (oldId === 'topic') {
    return newNodes.some((node) => node.id === 'topic') ? 'topic' : null
  }
  if (!oldId.startsWith('branch-')) {
    return newNodes.some((node) => node.id === oldId) ? oldId : null
  }

  const oldNode = oldNodes.find((node) => node.id === oldId)
  const stableUid = readMindMapNodeUid(oldNode)
  if (stableUid) {
    const byUid = findNodeIdByMindMapUid(newNodes, stableUid)
    if (byUid) return byUid
  }

  const segments = getMindMapTextSegments(oldId, oldNodes, oldConnections)
  const pathKey = mindMapNodePathKey(oldId, oldConnections)
  if (pathKey) {
    const byPath = findNodeIdByPathKey(newNodes, newConnections, pathKey)
    if (byPath) {
      const pathSegments = getMindMapTextSegments(byPath, newNodes, newConnections)
      if (!segments || textSegmentsEqual(segments, pathSegments)) {
        return byPath
      }
    }
  }

  if (segments) {
    const side: 'l' | 'r' = oldId.startsWith('branch-l-') ? 'l' : 'r'
    const sameSide = findNodeIdByTextSegmentsOnSide(segments, side, newNodes, newConnections)
    if (sameSide) return sameSide
    const otherSide: 'l' | 'r' = side === 'l' ? 'r' : 'l'
    const crossSide = findNodeIdByTextSegmentsOnSide(
      segments,
      otherSide,
      newNodes,
      newConnections
    )
    if (crossSide) return crossSide
  }

  return findNodeIdByOwnTextIdentity(
    oldId,
    oldNodes,
    oldConnections,
    newNodes,
    newConnections
  )
}

/**
 * Carry DOM-measured sizes across a mind-map tree rebuild (add/delete/reload).
 * Remapped measurements win; build-time estimates only fill gaps (usually the new node)
 * so Enter/Tab reloads do not jump from measured layout back to estimate layout.
 */
export function remapMindMapMeasuredDimensionsAfterReload(
  oldWidths: Record<string, number>,
  oldHeights: Record<string, number>,
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[]
): { widths: Record<string, number>; heights: Record<string, number> } {
  const widths: Record<string, number> = {}
  const heights: Record<string, number> = {}

  for (const [oldId, width] of Object.entries(oldWidths)) {
    const newId = remapMindMapNodeIdAfterReload(
      oldId,
      oldNodes,
      oldConnections,
      newNodes,
      newConnections
    )
    if (newId) widths[newId] = width
  }

  for (const [oldId, height] of Object.entries(oldHeights)) {
    const newId = remapMindMapNodeIdAfterReload(
      oldId,
      oldNodes,
      oldConnections,
      newNodes,
      newConnections
    )
    if (newId) heights[newId] = height
  }

  for (const node of newNodes) {
    const estimatedWidth = node.data?.estimatedWidth as number | undefined
    const estimatedHeight = node.data?.estimatedHeight as number | undefined
    if (estimatedWidth !== undefined && widths[node.id] === undefined) {
      widths[node.id] = estimatedWidth
    }
    if (estimatedHeight !== undefined && heights[node.id] === undefined) {
      heights[node.id] = estimatedHeight
    }
  }

  return { widths, heights }
}

/** Remap a selection list across a mind-map tree rebuild; drops unresolved ids. */
export function remapMindMapNodeIdsAfterReload(
  oldIds: string[],
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[]
): string[] {
  const remapped: string[] = []
  const seen = new Set<string>()
  for (const oldId of oldIds) {
    const next = remapMindMapNodeIdAfterReload(
      oldId,
      oldNodes,
      oldConnections,
      newNodes,
      newConnections
    )
    if (!next || seen.has(next)) continue
    seen.add(next)
    remapped.push(next)
  }
  return remapped
}

/** Keep collapse state across mind-map tree rebuilds (add/delete/reload). */
export function remapMindMapCollapsedPathsAfterReload(
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[],
  collapsedPaths: string[]
): string[] {
  const kept = new Set<string>()

  for (const path of collapsedPaths) {
    const directId = findNodeIdByPathKey(newNodes, newConnections, path)
    if (directId && mindMapNodeHasChildren(directId, newConnections)) {
      kept.add(path)
      continue
    }

    const oldId = findNodeIdByPathKey(oldNodes, oldConnections, path)
    if (!oldId) continue

    const segments = getMindMapTextSegments(oldId, oldNodes, oldConnections)
    if (!segments) continue

    const side: 'l' | 'r' = oldId.startsWith('branch-l-') ? 'l' : 'r'
    const newId = findNodeIdByTextSegmentsOnSide(segments, side, newNodes, newConnections)
    if (!newId || !mindMapNodeHasChildren(newId, newConnections)) continue

    const newPath = mindMapNodePathKey(newId, newConnections)
    if (newPath) kept.add(newPath)
  }

  return [...kept]
}

export function getMindMapCollapsedPaths(data: DiagramData | null | undefined): string[] {
  if (!data) return []
  const raw = data._collapsed_paths
  return Array.isArray(raw) ? raw.filter((p) => typeof p === 'string' && p.length > 0) : []
}

/** Node ids whose branch subtree is collapsed (the collapsed parents themselves). */
export function getMindMapCollapsedNodeIds(
  nodes: DiagramNode[],
  connections: Connection[],
  collapsedPaths: string[]
): Set<string> {
  const ids = new Set<string>()
  for (const path of collapsedPaths) {
    const id = findNodeIdByPathKey(nodes, connections, path)
    if (id) ids.add(id)
  }
  return ids
}

/** Descendant node ids hidden by collapse (parents stay visible). */
export function getMindMapCollapseHiddenIds(
  nodes: DiagramNode[],
  connections: Connection[],
  collapsedPaths: string[],
  getDescendantIds: (rootId: string) => Set<string>
): Set<string> {
  const hidden = new Set<string>()
  for (const path of collapsedPaths) {
    const nodeId = findNodeIdByPathKey(nodes, connections, path)
    if (!nodeId) continue
    for (const id of getDescendantIds(nodeId)) {
      if (id !== nodeId) hidden.add(id)
    }
  }
  return hidden
}

/** Collapsed nodes whose expand button should render (exclude nodes hidden by an ancestor collapse). */
export function getMindMapVisibleCollapsedNodeIds(
  nodes: DiagramNode[],
  connections: Connection[],
  collapsedPaths: string[],
  getDescendantIds: (rootId: string) => Set<string>
): Set<string> {
  const collapsed = getMindMapCollapsedNodeIds(nodes, connections, collapsedPaths)
  const hidden = getMindMapCollapseHiddenIds(
    nodes,
    connections,
    collapsedPaths,
    getDescendantIds
  )
  const visible = new Set<string>()
  for (const id of collapsed) {
    if (!hidden.has(id)) visible.add(id)
  }
  return visible
}

export function mindMapNodeHasChildren(nodeId: string, connections: Connection[]): boolean {
  return connections.some((c) => c.source === nodeId)
}

export function mindMapDescendantCount(
  nodeId: string,
  getDescendantIds: (rootId: string) => Set<string>
): number {
  return Math.max(0, getDescendantIds(nodeId).size - 1)
}

export function isMindMapPathCollapsed(
  nodeId: string,
  connections: Connection[],
  collapsedPaths: string[]
): boolean {
  const pathKey = mindMapNodePathKey(nodeId, connections)
  if (!pathKey) return false
  return collapsedPaths.includes(pathKey)
}

export function pruneMindMapCollapsedPaths(
  nodes: DiagramNode[],
  connections: Connection[],
  collapsedPaths: string[]
): string[] {
  return collapsedPaths.filter((path) => {
    const id = findNodeIdByPathKey(nodes, connections, path)
    if (!id || id === 'topic') return false
    return mindMapNodeHasChildren(id, connections)
  })
}

export function setMindMapCollapsedPaths(
  data: Record<string, unknown>,
  paths: string[]
): void {
  const pruned = paths.filter(Boolean)
  if (pruned.length === 0) {
    delete data._collapsed_paths
  } else {
    data._collapsed_paths = pruned
  }
}
