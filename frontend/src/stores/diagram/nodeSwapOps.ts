import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection } from '@/types'
import {
  findBridgePairSide,
  isBridgeMapPairNode,
  readBridgePairIndex,
} from '@/utils/bridgeMapIdentity'
import {
  BUBBLE_MAP_UID_DATA_KEY,
  BUBBLE_TOPIC_NODE_ID,
  isBubbleMapAttributeNode,
  stampBubbleAttributeData,
} from '@/utils/bubbleMapIdentity'
import { isCircleMapContextNode } from '@/utils/circleMapIdentity'
import {
  isDoubleBubbleRoleNode,
  readDoubleBubbleIndex,
  readDoubleBubbleRole,
} from '@/utils/doubleBubbleMapIdentity'
import {
  flowMapChildBelongsToStep,
  isFlowMapStepNode,
  isFlowMapSubstepNode,
  readFlowParentStepId,
  readFlowStepIndex,
  readFlowSubstepIndex,
} from '@/utils/flowMapIdentity'
import {
  isMultiFlowCauseNode,
  isMultiFlowEffectNode,
  readMultiFlowRole,
} from '@/utils/multiFlowMapIdentity'

import {
  recalculateBraceMapLayout,
  recalculateBubbleMapLayout,
  recalculateCircleMapLayout,
} from '../specLoader'
import {
  type FlowSubstepEntry,
  findFlowSubstepEntry,
  swapFlowMapCollectedSteps,
} from '../specLoader/flowMapSubsteps'
import { emitCtxEvent } from './events'
import type { DiagramContext } from './types'

export function useNodeSwapOpsSlice(ctx: DiagramContext) {
  function getNodeGroupIds(nodeId: string): Set<string> {
    const result = new Set<string>([nodeId])
    const dt = ctx.type.value
    if (!dt || !ctx.data.value) return result
    const nodes = ctx.data.value.nodes

    if (dt === 'bridge_map') {
      const node = nodes.find((n) => n.id === nodeId)
      if (node && isBridgeMapPairNode(node)) {
        const pairIndex = readBridgePairIndex(node)
        const left = findBridgePairSide(nodes, pairIndex, 'left')
        const right = findBridgePairSide(nodes, pairIndex, 'right')
        if (left) result.add(left.id)
        if (right) result.add(right.id)
      }
    } else if (dt === 'double_bubble_map') {
      const node = nodes.find((n) => n.id === nodeId)
      const role = node ? readDoubleBubbleRole(node) : null
      if (node && (role === 'leftDiff' || role === 'rightDiff')) {
        const pairIndex = readDoubleBubbleIndex(node)
        const partnerRole = role === 'leftDiff' ? 'rightDiff' : 'leftDiff'
        const partner = nodes.find(
          (n) => isDoubleBubbleRoleNode(n, partnerRole) && readDoubleBubbleIndex(n) === pairIndex
        )
        if (partner) result.add(partner.id)
      }
    } else if (dt === 'flow_map') {
      const stepNode = ctx.data.value.nodes.find((n) => n.id === nodeId)
      if (stepNode && isFlowMapStepNode(stepNode)) {
        ctx.data.value.nodes
          .filter((n) => isFlowMapSubstepNode(n) && flowMapChildBelongsToStep(n, stepNode))
          .forEach((n) => result.add(n.id))
      }
    } else if (dt === 'brace_map' && ctx.data.value.connections) {
      const childrenMap = new Map<string, string[]>()
      ctx.data.value.connections.forEach((c) => {
        if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
        const srcList = childrenMap.get(c.source)
        if (srcList) srcList.push(c.target)
      })
      const collectChildren = (id: string): void => {
        for (const childId of childrenMap.get(id) ?? []) {
          result.add(childId)
          collectChildren(childId)
        }
      }
      collectChildren(nodeId)
    } else if (dt === 'mindmap' || dt === 'mind_map') {
      return ctx.getMindMapDescendantIds(nodeId)
    } else if (dt === 'tree_map') {
      return ctx.getTreeMapDescendantIds(nodeId)
    }

    return result
  }

  function swapNodeText(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes) return false
    const src = ctx.data.value.nodes.find((n) => n.id === sourceId)
    const tgt = ctx.data.value.nodes.find((n) => n.id === targetId)
    if (!src || !tgt) return false
    const tmp = src.text
    src.text = tgt.text
    tgt.text = tmp
    return true
  }

  function swapBubbleMapNodes(sourceId: string, targetId: string): boolean {
    if (!swapNodeText(sourceId, targetId) || !ctx.data.value?.nodes) return false
    const recalculatedNodes = recalculateBubbleMapLayout(
      ctx.data.value.nodes,
      ctx.nodeDimensions.value
    )
    const recalcBubbles = recalculatedNodes.filter((n) => isBubbleMapAttributeNode(n))
    recalcBubbles.forEach((bubbleNode, i) => {
      bubbleNode.data = stampBubbleAttributeData(i, {
        ...bubbleNode.data,
        [BUBBLE_MAP_UID_DATA_KEY]: bubbleNode.id,
      })
    })
    ctx.data.value.nodes = recalculatedNodes
    ctx.data.value.connections = recalcBubbles.map((bubbleNode, i) => ({
      id: `edge-${BUBBLE_TOPIC_NODE_ID}-${bubbleNode.id}`,
      source: BUBBLE_TOPIC_NODE_ID,
      target: bubbleNode.id,
      style: { strokeColor: getMindmapBranchColor(i).border },
    }))
    return true
  }

  function swapCircleMapNodes(sourceId: string, targetId: string): boolean {
    if (!swapNodeText(sourceId, targetId) || !ctx.data.value?.nodes) return false
    if (!isCircleMapContextNode({ id: sourceId, type: 'bubble' })) return true
    ctx.data.value.nodes = recalculateCircleMapLayout(
      ctx.data.value.nodes,
      ctx.nodeDimensions.value
    )
    return true
  }

  function swapDoubleBubbleMapNodes(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes) return false
    const nodes = ctx.data.value.nodes
    const src = nodes.find((n) => n.id === sourceId)
    const tgt = nodes.find((n) => n.id === targetId)
    if (!src || !tgt) return false
    const srcRole = readDoubleBubbleRole(src)
    const tgtRole = readDoubleBubbleRole(tgt)
    if (srcRole === 'similarity' && tgtRole === 'similarity') {
      return swapNodeText(sourceId, targetId)
    }
    if (
      (srcRole === 'leftDiff' || srcRole === 'rightDiff') &&
      (tgtRole === 'leftDiff' || tgtRole === 'rightDiff')
    ) {
      const srcIdx = readDoubleBubbleIndex(src)
      const tgtIdx = readDoubleBubbleIndex(tgt)
      const srcLeft = nodes.find(
        (n) => isDoubleBubbleRoleNode(n, 'leftDiff') && readDoubleBubbleIndex(n) === srcIdx
      )
      const srcRight = nodes.find(
        (n) => isDoubleBubbleRoleNode(n, 'rightDiff') && readDoubleBubbleIndex(n) === srcIdx
      )
      const tgtLeft = nodes.find(
        (n) => isDoubleBubbleRoleNode(n, 'leftDiff') && readDoubleBubbleIndex(n) === tgtIdx
      )
      const tgtRight = nodes.find(
        (n) => isDoubleBubbleRoleNode(n, 'rightDiff') && readDoubleBubbleIndex(n) === tgtIdx
      )
      if (!srcLeft || !srcRight || !tgtLeft || !tgtRight) return false
      swapNodeText(srcLeft.id, tgtLeft.id)
      swapNodeText(srcRight.id, tgtRight.id)
      return true
    }
    return false
  }

  function swapFlowMapNodes(sourceId: string, targetId: string): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec || !ctx.data.value) return false
    const steps = spec.steps as Array<string | { id?: string; text: string }>
    const substepsList = spec.substeps as FlowSubstepEntry[]
    const srcNode = ctx.data.value.nodes.find((n) => n.id === sourceId)
    const tgtNode = ctx.data.value.nodes.find((n) => n.id === targetId)
    if (!srcNode || !tgtNode) return false

    const stepLabel = (step: string | { id?: string; text: string }): string =>
      typeof step === 'string' ? step : step.text

    if (isFlowMapStepNode(srcNode) && isFlowMapStepNode(tgtNode)) {
      const si = readFlowStepIndex(srcNode)
      const ti = readFlowStepIndex(tgtNode)
      if (si >= 0 && si < steps.length && ti >= 0 && ti < steps.length) {
        swapFlowMapCollectedSteps(steps, substepsList, si, ti)
        return ctx.loadFromSpec(spec, 'flow_map', { mergePreviousNodeStyles: true })
      }
      return false
    }

    if (isFlowMapSubstepNode(srcNode) && isFlowMapSubstepNode(tgtNode)) {
      const srcStep = readFlowStepIndex(srcNode)
      const srcSub = readFlowSubstepIndex(srcNode)
      const tgtStep = readFlowStepIndex(tgtNode)
      const tgtSub = readFlowSubstepIndex(tgtNode)
      if (srcStep < steps.length && tgtStep < steps.length && srcSub >= 0 && tgtSub >= 0) {
        const srcEntry = findFlowSubstepEntry(
          substepsList,
          stepLabel(steps[srcStep]),
          srcStep,
          readFlowParentStepId(srcNode) ?? undefined
        )
        const tgtEntry = findFlowSubstepEntry(
          substepsList,
          stepLabel(steps[tgtStep]),
          tgtStep,
          readFlowParentStepId(tgtNode) ?? undefined
        )
        if (
          srcEntry &&
          tgtEntry &&
          srcSub < srcEntry.substeps.length &&
          tgtSub < tgtEntry.substeps.length
        ) {
          const tmp = srcEntry.substeps[srcSub]
          srcEntry.substeps[srcSub] = tgtEntry.substeps[tgtSub]
          tgtEntry.substeps[tgtSub] = tmp
          return ctx.loadFromSpec(spec, 'flow_map', { mergePreviousNodeStyles: true })
        }
      }
      return false
    }
    return false
  }

  function moveFlowMapNode(sourceId: string, targetId: string): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec || !ctx.data.value) return false
    const steps = spec.steps as Array<string | { id?: string; text: string }>
    const substepsList = spec.substeps as FlowSubstepEntry[]
    const srcNode = ctx.data.value.nodes.find((n) => n.id === sourceId)
    const tgtNode = ctx.data.value.nodes.find((n) => n.id === targetId)
    const stepLabel = (step: string | { id?: string; text: string }): string =>
      typeof step === 'string' ? step : step.text

    let success: boolean

    if (srcNode && tgtNode && isFlowMapSubstepNode(srcNode) && isFlowMapStepNode(tgtNode)) {
      const srcStepIdx = readFlowStepIndex(srcNode)
      const srcSubIdx = readFlowSubstepIndex(srcNode)
      const tgtStepIdx = readFlowStepIndex(tgtNode)

      if (srcStepIdx === tgtStepIdx) return false
      if (srcStepIdx >= steps.length || tgtStepIdx >= steps.length || srcSubIdx < 0) return false

      const srcStepText = stepLabel(steps[srcStepIdx])
      const tgtStepText = stepLabel(steps[tgtStepIdx])
      const srcEntry = findFlowSubstepEntry(
        substepsList,
        srcStepText,
        srcStepIdx,
        readFlowParentStepId(srcNode) ?? undefined
      )
      if (!srcEntry || srcSubIdx >= srcEntry.substeps.length) return false

      const [movedText] = srcEntry.substeps.splice(srcSubIdx, 1)

      const tgtEntry = findFlowSubstepEntry(substepsList, tgtStepText, tgtStepIdx, tgtNode.id)
      if (tgtEntry) {
        tgtEntry.substeps.push(movedText)
      } else {
        substepsList.push({
          step: tgtStepText,
          stepId: tgtNode.id,
          stepIndex: tgtStepIdx,
          substeps: [movedText],
        })
      }

      success = ctx.loadFromSpec(spec, 'flow_map', { mergePreviousNodeStyles: true })
    } else {
      success = swapFlowMapNodes(sourceId, targetId)
    }

    if (success) {
      if (ctx.data.value?._customPositions) ctx.data.value._customPositions = {}
      if (ctx.data.value?._node_styles) ctx.data.value._node_styles = {}
      ctx.selectedNodes.value = []
      ctx.selectedConnectionId.value = null
      ctx.pushHistory('Move node')
      emitCtxEvent(ctx, 'diagram:operation_completed', { operation: 'move_branch' })
      ctx.viewBus.emit('diagram:branch_moved', {})
    }
    return success
  }

  function swapMultiFlowMapNodes(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes) return false
    const src = ctx.data.value.nodes.find((n) => n.id === sourceId)
    const tgt = ctx.data.value.nodes.find((n) => n.id === targetId)
    if (!src || !tgt) return false
    const srcRole = readMultiFlowRole(src)
    const tgtRole = readMultiFlowRole(tgt)
    if (!srcRole || srcRole !== tgtRole) return false
    if (
      (srcRole === 'cause' && !isMultiFlowCauseNode(src)) ||
      (srcRole === 'effect' && !isMultiFlowEffectNode(src))
    ) {
      return false
    }
    return swapNodeText(sourceId, targetId)
  }

  function swapBraceMapNodes(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes || !ctx.data.value?.connections) return false

    const targetIdSet = new Set(ctx.data.value.connections.map((c) => c.target))
    const rootId =
      ctx.data.value.nodes.find((n) => n.type === 'topic')?.id ??
      ctx.data.value.nodes.find((n) => !targetIdSet.has(n.id) && n.type !== 'label')?.id
    if (!rootId) return false

    const childrenMap = new Map<string, string[]>()
    ctx.data.value.connections.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      const srcList = childrenMap.get(c.source)
      if (srcList) srcList.push(c.target)
    })

    const srcParentConn = ctx.data.value.connections.find((c) => c.target === sourceId)
    const tgtParentConn = ctx.data.value.connections.find((c) => c.target === targetId)
    if (!srcParentConn || !tgtParentConn) return false

    const srcParent = srcParentConn.source
    const tgtParent = tgtParentConn.source
    const srcSiblings = childrenMap.get(srcParent) ?? []
    const tgtSiblings = childrenMap.get(tgtParent) ?? []
    const srcIdx = srcSiblings.indexOf(sourceId)
    const tgtIdx = tgtSiblings.indexOf(targetId)
    if (srcIdx < 0 || tgtIdx < 0) return false

    if (srcParent === tgtParent) {
      srcSiblings[srcIdx] = targetId
      srcSiblings[tgtIdx] = sourceId
    } else {
      srcSiblings[srcIdx] = targetId
      tgtSiblings[tgtIdx] = sourceId
    }

    const newConnections = ctx.data.value.connections.map((c: Connection) => {
      if (c.source === srcParent && c.target === sourceId) return { ...c, target: targetId }
      if (c.source === tgtParent && c.target === targetId) return { ...c, target: sourceId }
      if (c.source === sourceId) return { ...c, source: targetId }
      if (c.source === targetId) return { ...c, source: sourceId }
      if (c.target === sourceId) return { ...c, target: targetId }
      if (c.target === targetId) return { ...c, target: sourceId }
      return c
    })

    ctx.data.value.connections = newConnections

    const layoutNodes = recalculateBraceMapLayout(
      ctx.data.value.nodes,
      newConnections,
      ctx.nodeDimensions.value
    )
    ctx.data.value.nodes = layoutNodes
    return true
  }

  function moveBraceMapNode(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes || !ctx.data.value?.connections) return false

    const parentMap = new Map<string, string>()
    ctx.data.value.connections.forEach((c) => {
      parentMap.set(c.target, c.source)
    })

    function getDepth(nodeId: string): number {
      let depth = 0
      let current = nodeId
      while (parentMap.has(current)) {
        depth++
        const next = parentMap.get(current)
        if (next === undefined) break
        current = next
      }
      return depth
    }

    const srcDepth = getDepth(sourceId)
    const tgtDepth = getDepth(targetId)

    if (parentMap.get(sourceId) === targetId) return false

    let success: boolean

    if (srcDepth > tgtDepth) {
      const descendantIds = getNodeGroupIds(sourceId)
      if (descendantIds.has(targetId)) return false

      const oldParent = parentMap.get(sourceId)
      if (!oldParent) return false

      ctx.data.value.connections = ctx.data.value.connections.filter(
        (c) => !(c.source === oldParent && c.target === sourceId)
      )
      ctx.data.value.connections.push({
        id: `edge-${targetId}-${sourceId}`,
        source: targetId,
        target: sourceId,
      })

      const layoutNodes = recalculateBraceMapLayout(
        ctx.data.value.nodes,
        ctx.data.value.connections,
        ctx.nodeDimensions.value
      )
      ctx.data.value.nodes = layoutNodes
      success = true
    } else {
      success = swapBraceMapNodes(sourceId, targetId)
    }

    if (success) {
      if (ctx.data.value?._customPositions) ctx.data.value._customPositions = {}
      if (ctx.data.value?._node_styles) ctx.data.value._node_styles = {}
      ctx.selectedNodes.value = []
      ctx.selectedConnectionId.value = null
      ctx.pushHistory('Move node')
      emitCtxEvent(ctx, 'diagram:operation_completed', { operation: 'move_branch' })
      ctx.viewBus.emit('diagram:branch_moved', {})
    }
    return success
  }

  function swapBridgeMapPairs(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes) return false
    const nodes = ctx.data.value.nodes
    const src = nodes.find((n) => n.id === sourceId)
    const tgt = nodes.find((n) => n.id === targetId)
    if (!src || !tgt || !isBridgeMapPairNode(src) || !isBridgeMapPairNode(tgt)) return false
    const srcPairIdx = readBridgePairIndex(src)
    const tgtPairIdx = readBridgePairIndex(tgt)
    if (srcPairIdx < 0 || tgtPairIdx < 0 || srcPairIdx === tgtPairIdx) return false
    const srcLeft = findBridgePairSide(nodes, srcPairIdx, 'left')
    const srcRight = findBridgePairSide(nodes, srcPairIdx, 'right')
    const tgtLeft = findBridgePairSide(nodes, tgtPairIdx, 'left')
    const tgtRight = findBridgePairSide(nodes, tgtPairIdx, 'right')
    if (!srcLeft || !srcRight || !tgtLeft || !tgtRight) return false
    swapNodeText(srcLeft.id, tgtLeft.id)
    swapNodeText(srcRight.id, tgtRight.id)
    return true
  }

  function moveNodeBySwap(sourceId: string, targetId: string): boolean {
    const dt = ctx.type.value
    if (!dt || !ctx.data.value) return false

    let success: boolean
    switch (dt) {
      case 'bubble_map':
        success = swapBubbleMapNodes(sourceId, targetId)
        break
      case 'circle_map':
        success = swapCircleMapNodes(sourceId, targetId)
        break
      case 'double_bubble_map':
        success = swapDoubleBubbleMapNodes(sourceId, targetId)
        break
      case 'flow_map':
        return moveFlowMapNode(sourceId, targetId)
      case 'multi_flow_map':
        success = swapMultiFlowMapNodes(sourceId, targetId)
        break
      case 'brace_map':
        return moveBraceMapNode(sourceId, targetId)
      case 'bridge_map':
        success = swapBridgeMapPairs(sourceId, targetId)
        break
      default:
        return false
    }

    if (success) {
      if (ctx.data.value?._customPositions) ctx.data.value._customPositions = {}
      if (ctx.data.value?._node_styles) ctx.data.value._node_styles = {}
      ctx.selectedNodes.value = []
      ctx.selectedConnectionId.value = null
      ctx.pushHistory('Move node')
      emitCtxEvent(ctx, 'diagram:operation_completed', { operation: 'move_branch' })
      ctx.viewBus.emit('diagram:branch_moved', {})
    }
    return success
  }

  return { getNodeGroupIds, moveNodeBySwap }
}
