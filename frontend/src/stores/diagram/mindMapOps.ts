import { eventBus } from '@/composables/core/useEventBus'
import { DEFAULT_CENTER_X } from '@/composables/diagrams/layoutConfig'
import {
  inferMindMapThemeIdFromNodes,
  resolveActiveMindMapThemeId,
} from '@/config/mindMapThemes'
import { i18n } from '@/i18n'
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import { readMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'

import { useInlineRecommendationsStore } from '../inlineRecommendations'
import {
  distributeBranchesClockwise,
  findBranchByNodeId,
  loadMindMapSpec,
  nodesAndConnectionsToMindMapSpec,
} from '../specLoader'
import { collabForeignLockBlocksAnyId, emitCollabDeleteBlocked } from './collabHelpers'
import { emitEvent, getMindMapCurveExtents } from './events'
import {
  findNodeIdByPathKey,
  mergeMindMapReloadStyles,
  mindMapNodePathKey,
} from './mindMapStylePreservation'
import {
  isMindMapPathCollapsed,
  mindMapNodeHasChildren,
  pruneMindMapCollapsedPaths,
  remapMindMapCollapsedPathsAfterReload,
  setMindMapCollapsedPaths,
} from './mindMapCollapse'
import type { DiagramContext } from './types'
import type { SpecLoaderResult } from '../specLoader/types'

function defaultNewNodeText(): string {
  return String(i18n.global.t('diagram.editable.placeholder')).replace(/[….]{1,3}$/u, '')
}

function defaultNewChildText(): string {
  return String(i18n.global.t('diagram.newChild'))
}

function defaultLegacyBranchWithChildren(
  text: string,
  childText = defaultNewChildText()
): { text: string; children: { text: string }[] } {
  return {
    text,
    children: [{ text: `${childText} 1` }, { text: `${childText} 2` }],
  }
}

/** Legacy canvas: new top-level branches include two default children; v2: text only. */
function newTopLevelMindMapBranchSpec(
  text: string,
  childText = defaultNewChildText()
): { text: string; children?: { text: string }[] } {
  if (readMindMapV2VisualDesignActive()) {
    return { text }
  }
  return defaultLegacyBranchWithChildren(text, childText)
}

function resolvePathKeyForBranchSpec(
  branchSpec: { text: string; children?: { text: string }[] },
  rightBranches: ReturnType<typeof nodesAndConnectionsToMindMapSpec>['rightBranches'],
  leftBranches: ReturnType<typeof nodesAndConnectionsToMindMapSpec>['leftBranches']
): string | null {
  const rightIdx = rightBranches.indexOf(branchSpec)
  if (rightIdx >= 0) return `r/${rightIdx}`
  const leftIdx = leftBranches.indexOf(branchSpec)
  if (leftIdx >= 0) return `l/${leftIdx}`
  return null
}

/**
 * Retain DOM-measured widths/heights for node IDs that still exist after a
 * tree rebuild.  Nodes whose IDs survived the rebuild kept the same text, so
 * their DOM dimensions are unchanged.  Dropping only the stale entries avoids
 * a flicker where `recalculateMindMapColumnPositions` falls back to the less
 * accurate `estimateNodeWidth` heuristic for nodes whose ResizeObservers
 * won't re-fire (the DOM size didn't change, so the observer stays silent).
 */
function retainMeasuredDimensions(ctx: DiagramContext, newNodes: DiagramNode[]): void {
  const surviving = new Set(newNodes.map((n) => n.id))

  const widths = ctx.mindMapNodeWidths.value
  for (const id of Object.keys(widths)) {
    if (!surviving.has(id)) delete widths[id]
  }

  const heights = ctx.mindMapNodeHeights.value
  for (const id of Object.keys(heights)) {
    if (!surviving.has(id)) delete heights[id]
  }

  ctx.mindMapRecalcTrigger.value++
}

function getMindMapParentId(connections: Connection[], nodeId: string): string | null {
  return connections.find((c) => c.target === nodeId)?.source ?? null
}

function computeSiblingPathKey(
  nodeId: string,
  insertIndex: number,
  connections: Connection[]
): string | null {
  const parentId = getMindMapParentId(connections, nodeId)
  if (!parentId || parentId === 'topic') {
    const side = nodeId.startsWith('branch-l-') ? 'l' : 'r'
    return `${side}/${insertIndex}`
  }
  const parentPath = mindMapNodePathKey(parentId, connections)
  if (!parentPath) return null
  return `${parentPath}/${insertIndex}`
}

function selectAndEditByPathKey(
  ctx: DiagramContext,
  nodes: DiagramNode[],
  connections: Connection[],
  pathKey: string | null
): void {
  if (!pathKey) return
  const nodeId = findNodeIdByPathKey(nodes, connections, pathKey)
  if (!nodeId) return
  ctx.selectedNodes.value = [nodeId]
  ctx.mindMapRecalcTrigger.value++
  // Wait for Vue Flow to mount the new node before opening inline editor
  const EDIT_FOCUS_DELAY_MS = 120
  setTimeout(() => {
    eventBus.emit('node:edit_requested', { nodeId })
  }, EDIT_FOCUS_DELAY_MS)
}

function commitMindMapReloadWithSelect(
  ctx: DiagramContext,
  result: SpecLoaderResult,
  selectPathKey: string | null,
  historyLabel: string
): boolean {
  if (!ctx.data.value?.nodes || !ctx.data.value?.connections) return false
  commitMindMapReload(ctx, result)
  ctx.pushHistory(historyLabel)
  emitEvent('diagram:node_added', { node: null })
  selectAndEditByPathKey(ctx, result.nodes, result.connections, selectPathKey)
  return true
}

function commitMindMapReload(ctx: DiagramContext, result: SpecLoaderResult): void {
  if (!ctx.data.value?.nodes || !ctx.data.value?.connections) return

  const v2Visuals = readMindMapV2VisualDesignActive()

  if (v2Visuals && !ctx.data.value._mindmap_theme) {
    const inferred = inferMindMapThemeIdFromNodes(ctx.data.value.nodes)
    if (inferred) ctx.data.value._mindmap_theme = inferred
  }

  const mergedNodeStyles = mergeMindMapReloadStyles(
    ctx.data.value.nodes,
    ctx.data.value.connections,
    result.nodes,
    result.connections,
    ctx.data.value._node_styles,
    v2Visuals ? resolveActiveMindMapThemeId(ctx.data.value) : undefined
  )

  retainMeasuredDimensions(ctx, result.nodes)

  const oldNodes = ctx.data.value.nodes
  const oldConnections = ctx.data.value.connections

  ctx.data.value.nodes = result.nodes
  ctx.data.value.connections = result.connections
  ctx.data.value._node_styles = mergedNodeStyles

  if (v2Visuals) {
    const collapsedBefore = ctx.data.value._collapsed_paths ?? []
    const remapped = remapMindMapCollapsedPathsAfterReload(
      oldNodes,
      oldConnections,
      result.nodes,
      result.connections,
      collapsedBefore
    )
    const pruned = pruneMindMapCollapsedPaths(result.nodes, result.connections, remapped)
    setMindMapCollapsedPaths(ctx.data.value as Record<string, unknown>, pruned)
  }
}

export function useMindMapOpsSlice(ctx: DiagramContext) {
  const { type, data, selectedNodes, mindMapCurveExtentBaseline } = ctx

  function addMindMapBranch(
    side: 'left' | 'right',
    text = defaultNewNodeText(),
    childText = defaultNewChildText()
  ): boolean {
    if (readMindMapV2VisualDesignActive()) {
      return addMindMapBranchOnSide(side, text)
    }
    return addMindMapBranchClockwise(text, childText)
  }

  function addMindMapBranchClockwise(
    text = defaultNewNodeText(),
    childText = defaultNewChildText()
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const newBranch = newTopLevelMindMapBranchSpec(text, childText)

    const allBranches = [...spec.rightBranches, ...spec.leftBranches.slice().reverse()]
    allBranches.push(newBranch)
    const { rightBranches, leftBranches } = distributeBranchesClockwise(allBranches)
    const pathKey = resolvePathKeyForBranchSpec(newBranch, rightBranches, leftBranches)

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches,
      rightBranches,
      preserveLeftRight: true,
    })
    return commitMindMapReloadWithSelect(ctx, result, pathKey, 'Add branch')
  }

  function addMindMapBranchOnSide(
    side: 'left' | 'right',
    text = defaultNewNodeText()
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const newBranch = { text }
    const pathKey =
      side === 'left' ? `l/${spec.leftBranches.length}` : `r/${spec.rightBranches.length}`

    if (side === 'left') {
      spec.leftBranches.push(newBranch)
    } else {
      spec.rightBranches.push(newBranch)
    }

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })
    return commitMindMapReloadWithSelect(ctx, result, pathKey, 'Add branch')
  }

  function addMindMapChild(
    parentNodeId: string,
    text = defaultNewNodeText()
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const connections = data.value.connections
    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, connections)
    const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, parentNodeId)
    if (!found) return false

    const { branch } = found
    if (!branch.children) {
      branch.children = []
    }
    branch.children.push({ text })
    const parentPath = mindMapNodePathKey(parentNodeId, connections)
    const pathKey = parentPath ? `${parentPath}/${branch.children.length - 1}` : null

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })
    return commitMindMapReloadWithSelect(ctx, result, pathKey, 'Add child')
  }

  function removeMindMapNodes(nodeIds: string[]): number {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return 0
    if (!data.value?.nodes || !data.value?.connections) return 0

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const idsToRemove = new Set(nodeIds.filter((id) => id.startsWith('branch-')))

    if (collabForeignLockBlocksAnyId(ctx, idsToRemove)) {
      emitCollabDeleteBlocked()
      return 0
    }

    const toRemoveWithParent: {
      nodeId: string
      parentArray: { text: string; children?: unknown[] }[]
      indexInParent: number
    }[] = []
    idsToRemove.forEach((nodeId) => {
      const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, nodeId)
      if (found) {
        toRemoveWithParent.push({
          nodeId,
          parentArray: found.parentArray,
          indexInParent: found.indexInParent,
        })
      }
    })

    const depth = (id: string) => parseInt(id.split('-')[2] ?? '0', 10)
    toRemoveWithParent.sort((a, b) => {
      const dA = depth(a.nodeId)
      const dB = depth(b.nodeId)
      if (dA !== dB) return dB - dA
      return b.indexInParent - a.indexInParent
    })
    toRemoveWithParent.forEach(({ parentArray, indexInParent }) => {
      parentArray.splice(indexInParent, 1)
    })

    const deletedCount = toRemoveWithParent.length
    if (deletedCount === 0) return 0

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })
    commitMindMapReload(ctx, result)

    nodeIds.forEach((id) => {
      ctx.clearCustomPosition(id)
      ctx.clearNodeStyle(id)
      ctx.removeFromSelection(id)
    })
    ctx.pushHistory('Delete nodes')
    emitEvent('diagram:nodes_deleted', { nodeIds })
    return deletedCount
  }

  function getMindMapDescendantIds(rootNodeId: string): Set<string> {
    const connections = data.value?.connections ?? []
    const childrenMap = new Map<string, string[]>()
    connections.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      const srcList = childrenMap.get(c.source)
      if (srcList) srcList.push(c.target)
    })
    const result = new Set<string>([rootNodeId])
    function collect(id: string): void {
      for (const childId of childrenMap.get(id) ?? []) {
        result.add(childId)
        collect(childId)
      }
    }
    collect(rootNodeId)
    return result
  }

  function moveMindMapBranch(
    branchNodeId: string,
    targetType: 'topic' | 'child' | 'before' | 'after' | 'sibling',
    targetId?: string,
    _targetIndex?: number,
    cursorFlowX?: number
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false
    if (branchNodeId === 'topic') return false

    const centerX = DEFAULT_CENTER_X
    const extentsBefore = getMindMapCurveExtents(data.value.nodes, centerX)

    if (mindMapCurveExtentBaseline.value == null) {
      mindMapCurveExtentBaseline.value = { ...extentsBefore }
    }

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const sourceFound = findBranchByNodeId(spec.rightBranches, spec.leftBranches, branchNodeId)
    if (!sourceFound) return false

    const { branch, parentArray, indexInParent } = sourceFound
    const descendantIds = getMindMapDescendantIds(branchNodeId)

    if ((targetType === 'child' || targetType === 'before' || targetType === 'after') && targetId) {
      if (descendantIds.has(targetId)) return false
    }

    if (targetType === 'topic') {
      parentArray.splice(indexInParent, 1)
      const useLeft = cursorFlowX !== undefined && cursorFlowX < DEFAULT_CENTER_X
      if (useLeft) {
        spec.leftBranches.push(branch)
      } else {
        spec.rightBranches.push(branch)
      }
    } else if (targetType === 'child' && targetId) {
      const targetFound = findBranchByNodeId(spec.rightBranches, spec.leftBranches, targetId)
      if (!targetFound) return false
      parentArray.splice(indexInParent, 1)
      if (!targetFound.branch.children) targetFound.branch.children = []
      targetFound.branch.children.push(branch)
    } else if ((targetType === 'before' || targetType === 'after') && targetId) {
      const targetFound = findBranchByNodeId(spec.rightBranches, spec.leftBranches, targetId)
      if (!targetFound) return false

      const [removed] = parentArray.splice(indexInParent, 1)
      const targetParentArray = targetFound.parentArray
      let insertIdx =
        targetType === 'before' ? targetFound.indexInParent : targetFound.indexInParent + 1

      if (parentArray === targetParentArray && indexInParent < insertIdx) {
        insertIdx -= 1
      }
      targetParentArray.splice(insertIdx, 0, removed)
    } else if (targetType === 'sibling' && targetId !== undefined) {
      const targetFound = findBranchByNodeId(spec.rightBranches, spec.leftBranches, targetId)
      if (!targetFound) return false
      if (descendantIds.has(targetId)) return false

      const targetBranch = targetFound.branch
      const targetParentArray = targetFound.parentArray
      const targetIdx = targetFound.indexInParent

      const isSameParent = parentArray === targetParentArray

      if (isSameParent) {
        const [removed] = parentArray.splice(indexInParent, 1)
        const adjustedTargetIdx = indexInParent < targetIdx ? targetIdx - 1 : targetIdx
        const [removedTarget] = parentArray.splice(adjustedTargetIdx, 1)
        if (indexInParent < targetIdx) {
          parentArray.splice(indexInParent, 0, removedTarget)
          parentArray.splice(targetIdx, 0, removed)
        } else {
          parentArray.splice(targetIdx, 0, removed)
          parentArray.splice(indexInParent, 0, removedTarget)
        }
      } else {
        parentArray.splice(indexInParent, 1)
        targetParentArray.splice(targetIdx, 1)
        parentArray.splice(indexInParent, 0, targetBranch)
        targetParentArray.splice(targetIdx, 0, branch)
      }
    } else {
      return false
    }

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })
    commitMindMapReload(ctx, result)
    selectedNodes.value = []
    ctx.selectedConnectionId.value = null
    ctx.pushHistory('Move branch')
    emitEvent('diagram:operation_completed', { operation: 'move_branch' })
    eventBus.emit('diagram:loaded', { diagramType: type.value || 'mindmap' })
    eventBus.emit('diagram:branch_moved', {})

    const targetDescendantIds =
      (targetType === 'sibling' && targetId) || (targetType === 'child' && targetId)
        ? getMindMapDescendantIds(targetId)
        : new Set<string>()
    ;[...descendantIds, ...targetDescendantIds].forEach((id) => {
      useInlineRecommendationsStore().invalidateForNode(id)
    })

    return true
  }

  function applyMindMapSpecReload(
    topic: string,
    leftBranches: ReturnType<typeof nodesAndConnectionsToMindMapSpec>['leftBranches'],
    rightBranches: ReturnType<typeof nodesAndConnectionsToMindMapSpec>['rightBranches'],
    historyLabel: string,
    selectPathKey: string | null = null
  ): boolean {
    const result = loadMindMapSpec({
      topic,
      leftBranches,
      rightBranches,
      preserveLeftRight: true,
    })
    return commitMindMapReloadWithSelect(ctx, result, selectPathKey, historyLabel)
  }

  function getMindMapStructureMode(): 'balanced' | 'right' {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return 'balanced'
    if (!data.value?.nodes || !data.value?.connections) return 'balanced'
    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    return spec.leftBranches.length === 0 ? 'right' : 'balanced'
  }

  function setMindMapStructureMode(mode: 'balanced' | 'right'): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const allBranches = [...spec.rightBranches, ...spec.leftBranches.slice().reverse()]

    if (mode === 'right') {
      return applyMindMapSpecReload(spec.topic, [], allBranches, 'Structure: right')
    }

    const { rightBranches, leftBranches } = distributeBranchesClockwise(allBranches)
    return applyMindMapSpecReload(spec.topic, leftBranches, rightBranches, 'Structure: balanced')
  }

  function addMindMapSibling(
    nodeId: string,
    text = defaultNewNodeText(),
    position: 'above' | 'below' = 'below'
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false
    if (nodeId === 'topic') return false

    const connections = data.value.connections
    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, connections)
    const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, nodeId)
    if (!found) return false

    const insertIndex =
      position === 'above' ? found.indexInParent : found.indexInParent + 1
    const parentId = getMindMapParentId(connections, nodeId)
    const newSibling =
      parentId === 'topic'
        ? newTopLevelMindMapBranchSpec(text)
        : { text }
    found.parentArray.splice(insertIndex, 0, newSibling)
    const pathKey = computeSiblingPathKey(nodeId, insertIndex, connections)

    return applyMindMapSpecReload(
      spec.topic,
      spec.leftBranches,
      spec.rightBranches,
      position === 'above' ? 'Add sibling above' : 'Add sibling',
      pathKey
    )
  }

  function insertMindMapSiblingsFromLines(
    anchorNodeId: string,
    lines: string[],
    options?: { topicSide?: 'left' | 'right' }
  ): number {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return 0
    if (!data.value?.nodes || !data.value?.connections) return 0

    const labels = lines.map((line) => line.trim()).filter(Boolean)
    if (labels.length === 0) return 0

    if (collabForeignLockBlocksAnyId(ctx, [anchorNodeId])) {
      emitCollabDeleteBlocked()
      return 0
    }

    const connections = data.value.connections
    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, connections)
    let selectPathKey: string | null = null

    if (anchorNodeId === 'topic') {
      const side = options?.topicSide ?? 'right'
      const branches = side === 'left' ? spec.leftBranches : spec.rightBranches
      const startIndex = branches.length
      branches.push(...labels.map((text) => ({ text })))
      selectPathKey = `${side === 'left' ? 'l' : 'r'}/${startIndex + labels.length - 1}`
    } else {
      const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, anchorNodeId)
      if (!found) return 0

      const insertIndex = found.indexInParent + 1
      found.parentArray.splice(insertIndex, 0, ...labels.map((text) => ({ text })))
      selectPathKey = computeSiblingPathKey(
        anchorNodeId,
        insertIndex + labels.length - 1,
        connections
      )
    }

    const historyLabel = String(
      i18n.global.t('diagram.history.pasteSiblings', { count: labels.length })
    )
    const ok = applyMindMapSpecReload(
      spec.topic,
      spec.leftBranches,
      spec.rightBranches,
      historyLabel,
      selectPathKey
    )
    return ok ? labels.length : 0
  }

  function insertMindMapParentBranch(
    nodeId: string,
    text = defaultNewNodeText()
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false
    if (nodeId === 'topic') return false

    const connections = data.value.connections
    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, connections)
    const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, nodeId)
    if (!found) return false

    const pathKey = mindMapNodePathKey(nodeId, connections)
    if (!pathKey) return false

    const { branch, parentArray, indexInParent } = found
    parentArray.splice(indexInParent, 1, { text, children: [branch] })

    return applyMindMapSpecReload(
      spec.topic,
      spec.leftBranches,
      spec.rightBranches,
      'Insert parent branch',
      pathKey
    )
  }

  function performMindMapDirectionalAdd(
    nodeId: string,
    direction: 'top' | 'bottom' | 'left' | 'right'
  ): boolean {
    if (!readMindMapV2VisualDesignActive()) return false
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false

    if (nodeId === 'topic') {
      if (direction === 'left') return addMindMapBranchOnSide('left')
      if (direction === 'right') return addMindMapBranchOnSide('right')
      return false
    }

    const isLeftBranch = nodeId.startsWith('branch-l-')
    const outward: 'left' | 'right' = isLeftBranch ? 'left' : 'right'
    const inward: 'left' | 'right' = isLeftBranch ? 'right' : 'left'

    if (direction === 'top') return addMindMapSibling(nodeId, defaultNewNodeText(), 'above')
    if (direction === 'bottom') return addMindMapSibling(nodeId, defaultNewNodeText(), 'below')
    if (direction === outward) return addMindMapChild(nodeId)
    if (direction === inward) return insertMindMapParentBranch(nodeId)
    return false
  }

  function expandMindMapPathToNode(nodeId: string): boolean {
    if (!readMindMapV2VisualDesignActive()) return false
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false
    if (!nodeId || nodeId === 'topic') return false

    const connections = data.value.connections
    let paths = [...(data.value._collapsed_paths ?? [])]
    let changed = false

    const idsToExpand = new Set<string>()
    let current: string | undefined = nodeId
    while (current && current !== 'topic') {
      const parent = connections.find((c) => c.target === current)?.source
      if (parent && mindMapNodeHasChildren(parent, connections)) {
        idsToExpand.add(parent)
      }
      current = parent
    }

    for (const id of idsToExpand) {
      const pathKey = mindMapNodePathKey(id, connections)
      if (!pathKey || !paths.includes(pathKey)) continue
      paths = paths.filter((p) => p !== pathKey)
      changed = true
    }

    if (!changed) return false
    setMindMapCollapsedPaths(data.value as Record<string, unknown>, paths)
    ctx.mindMapRecalcTrigger.value++
    return true
  }

  function applyMindMapSubgraphPreview(result: SpecLoaderResult): void {
    if (!readMindMapV2VisualDesignActive()) return
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return
    commitMindMapReload(ctx, result)
    ctx.mindMapRecalcTrigger.value++
    emitEvent('diagram:operation_completed', { operation: 'subgraph_preview' })
  }

  function restoreMindMapSubgraphSnapshot(snapshot: {
    nodes: DiagramNode[]
    connections: Connection[]
    nodeStyles?: Record<string, NodeStyle>
    collapsedPaths?: string[]
  }): void {
    if (!readMindMapV2VisualDesignActive()) return
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return
    if (!data.value) return
    data.value.nodes = snapshot.nodes
    data.value.connections = snapshot.connections
    data.value._node_styles = snapshot.nodeStyles
    setMindMapCollapsedPaths(data.value as Record<string, unknown>, snapshot.collapsedPaths ?? [])
    ctx.mindMapRecalcTrigger.value++
  }

  function clearMindMapSubgraphPreviewTags(): void {
    if (!readMindMapV2VisualDesignActive()) return
    if (!data.value?.nodes) return
    for (const node of data.value.nodes) {
      if (node.data && (node.data as Record<string, unknown>).subgraphPreview) {
        const next = { ...(node.data as Record<string, unknown>) }
        delete next.subgraphPreview
        node.data = next
      }
    }
  }

  function toggleMindMapCollapse(nodeId: string): boolean {
    if (!readMindMapV2VisualDesignActive()) return false
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false
    if (nodeId === 'topic') return false
    if (!mindMapNodeHasChildren(nodeId, data.value.connections)) return false

    const pathKey = mindMapNodePathKey(nodeId, data.value.connections)
    if (!pathKey) return false

    const current = data.value._collapsed_paths ?? []
    const collapsed = isMindMapPathCollapsed(nodeId, data.value.connections, current)
    const next = collapsed
      ? current.filter((p) => p !== pathKey)
      : [...current, pathKey]

    setMindMapCollapsedPaths(data.value as Record<string, unknown>, next)
    ctx.mindMapRecalcTrigger.value++
    ctx.pushHistory(collapsed ? 'Expand branch' : 'Collapse branch')
    emitEvent('diagram:operation_completed', { operation: collapsed ? 'expand_branch' : 'collapse_branch' })
    return true
  }

  return {
    addMindMapBranch,
    addMindMapBranchOnSide,
    addMindMapChild,
    addMindMapSibling,
    insertMindMapSiblingsFromLines,
    insertMindMapParentBranch,
    performMindMapDirectionalAdd,
    removeMindMapNodes,
    getMindMapDescendantIds,
    moveMindMapBranch,
    getMindMapStructureMode,
    setMindMapStructureMode,
    toggleMindMapCollapse,
    expandMindMapPathToNode,
    applyMindMapSubgraphPreview,
    restoreMindMapSubgraphSnapshot,
    clearMindMapSubgraphPreviewTags,
  }
}
