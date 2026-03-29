import { eventBus } from '@/composables/core/useEventBus'
import { DEFAULT_CENTER_X } from '@/composables/diagrams/layoutConfig'
import { i18n } from '@/i18n'
import type { DiagramNode, Position } from '@/types'

import { useInlineRecommendationsStore } from '../inlineRecommendations'
import {
  distributeBranchesClockwise,
  findBranchByNodeId,
  loadMindMapSpec,
  nodesAndConnectionsToMindMapSpec,
} from '../specLoader'
import { collabForeignLockBlocksAnyId, emitCollabDeleteBlocked } from './collabHelpers'
import { emitEvent, getMindMapCurveExtents } from './events'
import type { DiagramContext } from './types'

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

export function useMindMapOpsSlice(ctx: DiagramContext) {
  const { type, data, selectedNodes, mindMapCurveExtentBaseline } = ctx

  function addMindMapBranch(
    _side: 'left' | 'right',
    text = String(i18n.global.t('diagram.newBranch')),
    childText = String(i18n.global.t('diagram.newChild'))
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const newBranch = {
      text,
      children: [{ text: `${childText} 1` }, { text: `${childText} 2` }],
    }

    const allBranches = [...spec.rightBranches, ...spec.leftBranches.slice().reverse()]
    allBranches.push(newBranch)
    const { rightBranches, leftBranches } = distributeBranchesClockwise(allBranches)

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches,
      rightBranches,
      preserveLeftRight: true,
    })
    retainMeasuredDimensions(ctx, result.nodes)

    data.value.nodes = result.nodes
    data.value.connections = result.connections
    const centerX = DEFAULT_CENTER_X
    const extentsAfter = getMindMapCurveExtents(result.nodes, centerX)
    const baseline = mindMapCurveExtentBaseline.value
    console.log('[BranchMove] curve length after add branch', extentsAfter)
    if (baseline) {
      console.log('[BranchMove] curve length change vs original', {
        leftDelta: extentsAfter.left - baseline.left,
        rightDelta: extentsAfter.right - baseline.right,
      })
    }
    ctx.pushHistory('Add branch')
    emitEvent('diagram:node_added', { node: null })
    return true
  }

  function addMindMapChild(parentNodeId: string, text = String(i18n.global.t('diagram.newChild'))): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, parentNodeId)
    if (!found) return false

    const { branch } = found
    if (!branch.children) {
      branch.children = []
    }
    branch.children.push({ text })

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })
    retainMeasuredDimensions(ctx, result.nodes)

    data.value.nodes = result.nodes
    data.value.connections = result.connections
    const centerX = DEFAULT_CENTER_X
    const extentsAfter = getMindMapCurveExtents(result.nodes, centerX)
    const baseline = mindMapCurveExtentBaseline.value
    console.log('[BranchMove] curve length after add child', extentsAfter)
    if (baseline) {
      console.log('[BranchMove] curve length change vs original', {
        leftDelta: extentsAfter.left - baseline.left,
        rightDelta: extentsAfter.right - baseline.right,
      })
    }
    ctx.pushHistory('Add child')
    emitEvent('diagram:node_added', { node: null })
    return true
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
    retainMeasuredDimensions(ctx, result.nodes)

    data.value.nodes = result.nodes
    data.value.connections = result.connections
    const centerX = DEFAULT_CENTER_X
    const extentsAfter = getMindMapCurveExtents(result.nodes, centerX)
    const baseline = mindMapCurveExtentBaseline.value
    console.log('[BranchMove] curve length after remove nodes', extentsAfter)
    if (baseline) {
      console.log('[BranchMove] curve length change vs original', {
        leftDelta: extentsAfter.left - baseline.left,
        rightDelta: extentsAfter.right - baseline.right,
      })
    }
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
    targetType: 'topic' | 'child' | 'sibling',
    targetId?: string,
    targetIndex?: number,
    cursorFlowX?: number
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    console.log('[BranchMove] start', { branchNodeId, targetType, targetId })

    const centerX = DEFAULT_CENTER_X
    const extentsBefore = getMindMapCurveExtents(data.value.nodes, centerX)
    console.log('[BranchMove] curve length before', extentsBefore)

    if (mindMapCurveExtentBaseline.value == null) {
      mindMapCurveExtentBaseline.value = { ...extentsBefore }
      console.log(
        '[BranchMove] baseline captured (first move fallback)',
        mindMapCurveExtentBaseline.value
      )
    }

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    console.log('[BranchMove] spec from nodes', {
      leftCount: spec.leftBranches.length,
      rightCount: spec.rightBranches.length,
      left: spec.leftBranches.map((b) => ({ text: b.text, childCount: b.children?.length ?? 0 })),
      right: spec.rightBranches.map((b) => ({
        text: b.text,
        childCount: b.children?.length ?? 0,
      })),
    })
    const sourceFound = findBranchByNodeId(spec.rightBranches, spec.leftBranches, branchNodeId)
    if (!sourceFound) return false

    const { branch, parentArray, indexInParent } = sourceFound
    const descendantIds = getMindMapDescendantIds(branchNodeId)

    if (targetType === 'child' && targetId) {
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

    const sourceParent =
      parentArray === spec.leftBranches
        ? 'left-top'
        : parentArray === spec.rightBranches
          ? 'right-top'
          : 'child'
    const targetLabel =
      targetType === 'topic'
        ? `topic (${cursorFlowX !== undefined && cursorFlowX < DEFAULT_CENTER_X ? 'left' : 'right'})`
        : targetType === 'child'
          ? `child of ${targetId}`
          : `sibling of ${targetId}`
    console.log('[BranchMove] node moved', {
      branchNodeId,
      from: sourceParent,
      to: targetLabel,
    })

    console.log('[BranchMove] spec after move', {
      left: spec.leftBranches.map((b) => ({ text: b.text, childCount: b.children?.length ?? 0 })),
      right: spec.rightBranches.map((b) => ({
        text: b.text,
        childCount: b.children?.length ?? 0,
      })),
    })
    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })
    retainMeasuredDimensions(ctx, result.nodes)

    const extentsAfter = getMindMapCurveExtents(result.nodes, centerX)
    console.log('[BranchMove] curve length after', extentsAfter)
    const baseline = mindMapCurveExtentBaseline.value
    console.log('[BranchMove] curve length change vs previous', {
      leftDelta: extentsAfter.left - extentsBefore.left,
      rightDelta: extentsAfter.right - extentsBefore.right,
    })
    if (baseline) {
      console.log('[BranchMove] curve length change vs original', {
        leftDelta: extentsAfter.left - baseline.left,
        rightDelta: extentsAfter.right - baseline.right,
      })
    }

    const branchPositions = result.nodes
      .filter((n): n is DiagramNode & { position: Position } =>
        Boolean(n.type === 'branch' && n.position)
      )
      .map((n) => ({ id: n.id, x: n.position.x, y: n.position.y }))
    console.log('[BranchMove] result positions', { branchPositions })

    const current = data.value as Record<string, unknown>
    const { _layout, _customPositions, _node_styles, ...rest } = current
    data.value = {
      ...rest,
      type: type.value,
      nodes: result.nodes,
      connections: result.connections,
      _customPositions: {},
      _node_styles: {},
    } as typeof data.value
    selectedNodes.value = []
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

  return {
    addMindMapBranch,
    addMindMapChild,
    removeMindMapNodes,
    getMindMapDescendantIds,
    moveMindMapBranch,
  }
}
