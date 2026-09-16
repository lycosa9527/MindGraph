import {
  omitNodeStyleLayoutSizes,
  pickFormatBrushStyle,
} from '@/composables/canvasToolbar/formatBrushStyle'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import { i18n } from '@/i18n'
import type { Connection, DiagramNode, DiagramType } from '@/types'
import {
  BRIDGE_MAP_UID_DATA_KEY,
  type BridgePairSide,
  isBridgeMapPairNode,
  stampBridgePairData,
  takeBridgeMapStableId,
} from '@/utils/bridgeMapIdentity'
import {
  BUBBLE_MAP_UID_DATA_KEY,
  BUBBLE_TOPIC_NODE_ID,
  isBubbleMapAttributeNode,
  stampBubbleAttributeData,
  takeBubbleMapStableId,
} from '@/utils/bubbleMapIdentity'
import {
  CIRCLE_BOUNDARY_NODE_ID,
  CIRCLE_MAP_UID_DATA_KEY,
  CIRCLE_TOPIC_NODE_ID,
  isCircleMapContextNode,
  stampCircleContextData,
  takeCircleMapStableId,
} from '@/utils/circleMapIdentity'
import {
  flowMapChildBelongsToStep,
  isFlowMapStepNode,
  isFlowMapSubstepNode,
} from '@/utils/flowMapIdentity'
import { mindMapBranchNumberMapFromData } from '@/utils/mindMapBranchNumbering'
import { isSessionMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'
import {
  MULTI_FLOW_EVENT_NODE_ID,
  MULTI_FLOW_UID_DATA_KEY,
  isMultiFlowCauseNode,
  isMultiFlowEffectNode,
  readMultiFlowRole,
  stampMultiFlowData,
  takeMultiFlowMapStableId,
} from '@/utils/multiFlowMapIdentity'
import { resolveNodeShape } from '@/utils/nodeShapeStyle'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

import { useConceptMapRelationshipStore } from '../conceptMapRelationship'
import {
  recalculateBubbleMapLayout,
  recalculateCircleMapLayout,
  recalculateMultiFlowMapLayout,
} from '../specLoader'
import {
  estimateNodeWidth as estimateMindMapBranchWidth,
  estimateNumberedBranchWidth,
  estimateTopicNodeHeight,
  estimateTopicNodeWidth,
  measureBranchNodeHeight as measureMindMapBranchHeight,
  measureNumberedBranchHeight,
  measureNumberedBranchUnderlineHeight,
} from '../specLoader/mindMap'
import { applyTreeMapTopicLayoutToNodes } from '../specLoader/treeMapTopicLayout'
import { isLearningSheetBlankDisplayText } from '../specLoader/utils'
import { collabForeignLockBlocksAnyId, emitCollabDeleteBlocked } from './collabHelpers'
import { emitCtxEvent } from './events'
import { syncMindMapSummaryNodeText } from './mindMapSummaryOps'
import { isDiagramPresentationReadOnly } from './presentationReadOnlyGuard'
import type { DiagramContext } from './types'

/**
 * Layouts that mix Pinia nodeDimensions with text metrics must drop cached DOM size when label
 * text changes; otherwise the next layout pass keeps the pre–KaTeX box (same issue as circle map).
 */
function shouldInvalidateNodeDimensionsOnTextEdit(
  diagramType: DiagramType,
  nodeId: string
): boolean {
  switch (diagramType) {
    case 'multi_flow_map':
    case 'circle_map':
    case 'bubble_map':
    case 'tree_map':
    case 'flow_map':
    case 'brace_map':
    case 'double_bubble_map':
    case 'bridge_map':
      return true
    default:
      return false
  }
}

export function useNodeManagementSlice(ctx: DiagramContext) {
  function updateNode(nodeId: string, updates: Partial<DiagramNode>): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (!ctx.data.value?.nodes) return false

    const nodeIndex = ctx.data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    const oldNode = ctx.data.value.nodes[nodeIndex]
    let merged: DiagramNode = {
      ...oldNode,
      ...updates,
    }
    if (updates.style !== undefined) {
      merged = {
        ...merged,
        style: { ...(oldNode.style || {}), ...updates.style },
      }
      if (
        (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map') &&
        Object.keys(updates.style).length > 0
      ) {
        merged = {
          ...merged,
          style: omitNodeStyleLayoutSizes(merged.style) ?? {},
        }
        if (!ctx.data.value._node_styles) {
          ctx.data.value._node_styles = {}
        }
        ctx.data.value._node_styles[nodeId] = {
          ...(ctx.data.value._node_styles[nodeId] || {}),
          ...pickFormatBrushStyle(merged.style),
        }
      }
    }

    // Keep data.label in sync with text so vue-flow nodes render the latest label.
    if ('text' in updates && typeof merged.text === 'string' && merged.data != null) {
      ;(merged.data as Record<string, unknown>).label = merged.text
    }

    if (
      (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map') &&
      'text' in updates &&
      typeof merged.text === 'string'
    ) {
      syncMindMapSummaryNodeText(ctx.data.value, nodeId, merged.text)
    }

    const treeTopicLayoutBump =
      ctx.type.value === 'tree_map' &&
      nodeId === 'tree-topic' &&
      (('text' in updates && updates.text !== undefined) ||
        (updates.style &&
          (updates.style.fontSize !== undefined ||
            updates.style.fontWeight !== undefined ||
            updates.style.fontFamily !== undefined)))

    if (treeTopicLayoutBump) {
      delete ctx.nodeDimensions.value['tree-topic']
      ctx.data.value.nodes = applyTreeMapTopicLayoutToNodes(ctx.data.value.nodes, nodeIndex, merged)
      ctx.layoutRecalcTrigger.value++
    } else {
      ctx.data.value.nodes[nodeIndex] = merged
    }

    if (ctx.type.value === 'concept_map' && nodeId === 'topic' && 'text' in updates) {
      const dr = ctx.data.value as Record<string, unknown>
      const raw = updates.text
      dr.focus_question = typeof raw === 'string' ? raw.trim() : ''
    }

    // Sync dimension-label text to data.dimension for brace_map, tree_map, bridge_map
    if (
      nodeId === 'dimension-label' &&
      (ctx.type.value === 'brace_map' ||
        ctx.type.value === 'tree_map' ||
        ctx.type.value === 'bridge_map') &&
      'text' in updates
    ) {
      const d = ctx.data.value as Record<string, unknown>
      const text = updates.text ?? ''
      d.dimension = text
      if (ctx.type.value === 'bridge_map') {
        d.relating_factor = text
      }
    }

    if (
      ctx.type.value &&
      'text' in updates &&
      shouldInvalidateNodeDimensionsOnTextEdit(ctx.type.value, nodeId)
    ) {
      delete ctx.nodeDimensions.value[nodeId]
      if (ctx.type.value === 'flow_map') {
        ctx.layoutRecalcTrigger.value++
      }
    }

    if (
      (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map') &&
      'text' in updates &&
      updates.text !== undefined &&
      nodeId !== 'topic'
    ) {
      const currentNode = ctx.data.value.nodes[nodeIndex]
      const nodeData = currentNode.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
      const newText = updates.text ?? ''
      const diagramData = ctx.data.value as {
        isLearningSheet?: boolean
        is_learning_sheet?: boolean
      }
      const isLearningSheetActive =
        diagramData.isLearningSheet === true || diagramData.is_learning_sheet === true
      const isLearningSheetBlankUpdate =
        isLearningSheetActive &&
        typeof nodeData?.hiddenAnswer === 'string' &&
        nodeData.hiddenAnswer.trim().length > 0 &&
        (nodeData?.hidden === true || isLearningSheetBlankDisplayText(newText))

      if (!isLearningSheetBlankUpdate) {
        const nodeStyle = {
          ...(ctx.data.value._node_styles?.[nodeId] || {}),
          ...(currentNode.style || {}),
        }
        const numberMap = mindMapBranchNumberMapFromData(ctx.data.value)
        const prefix = numberMap.get(nodeId) ?? ''
        const freshWidth = estimateNumberedBranchWidth(newText, prefix, nodeId, nodeStyle)
        const shape = resolveMindMapNodeShape(
          { id: nodeId, type: currentNode.type ?? 'branch', style: nodeStyle },
          ctx.data.value._mindmap_diagram_style as string | undefined
        )
        const freshHeight =
          shape === 'underline'
            ? measureNumberedBranchUnderlineHeight(newText, prefix, nodeId, nodeStyle)
            : measureNumberedBranchHeight(newText, prefix, nodeId, nodeStyle)
        ctx.data.value.nodes[nodeIndex] = {
          ...ctx.data.value.nodes[nodeIndex],
          data: {
            ...ctx.data.value.nodes[nodeIndex].data,
            estimatedWidth: freshWidth,
            estimatedHeight: freshHeight,
          },
        }
        // Drop stale DOM height so the next restack uses the fresh estimate immediately;
        // BranchNode ResizeObserver will replace it with the real box on the next frame.
        if (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map') {
          ctx.mindMapNodeHeights.value[nodeId] = freshHeight
          ctx.mindMapNodeWidths.value[nodeId] = freshWidth
          ctx.scheduleMindMapRecalc()
        }
      }
    }

    if (
      ctx.type.value === 'multi_flow_map' &&
      updates.style &&
      (updates.style.fontSize !== undefined ||
        updates.style.fontWeight !== undefined ||
        updates.style.fontFamily !== undefined)
    ) {
      delete ctx.nodeDimensions.value[nodeId]
      ctx.multiFlowMapRecalcTrigger.value++
    }

    if (
      ctx.type.value === 'bubble_map' &&
      updates.style &&
      (updates.style.fontSize !== undefined ||
        updates.style.fontWeight !== undefined ||
        updates.style.fontFamily !== undefined) &&
      (nodeId === BUBBLE_TOPIC_NODE_ID || oldNode.type === 'bubble' || oldNode.type === 'child')
    ) {
      delete ctx.nodeDimensions.value[nodeId]
      ctx.layoutRecalcTrigger.value++
    }

    if (
      ctx.type.value === 'flow_map' &&
      updates.style &&
      (updates.style.fontSize !== undefined ||
        updates.style.fontWeight !== undefined ||
        updates.style.fontFamily !== undefined) &&
      (nodeId === 'flow-topic' || oldNode.type === 'flow' || oldNode.type === 'flowSubstep')
    ) {
      delete ctx.nodeDimensions.value[nodeId]
      ctx.layoutRecalcTrigger.value++
    }

    if (
      ctx.type.value === 'brace_map' &&
      updates.style &&
      (updates.style.fontSize !== undefined ||
        updates.style.fontWeight !== undefined ||
        updates.style.fontFamily !== undefined) &&
      (nodeId === 'brace-whole' || oldNode.type === 'brace' || nodeId === 'dimension-label')
    ) {
      delete ctx.nodeDimensions.value[nodeId]
      ctx.layoutRecalcTrigger.value++
    }

    if (
      ctx.type.value === 'double_bubble_map' &&
      updates.style &&
      (updates.style.fontSize !== undefined ||
        updates.style.fontWeight !== undefined ||
        updates.style.fontFamily !== undefined)
    ) {
      delete ctx.nodeDimensions.value[nodeId]
      ctx.viewBus.emit('diagram:double_bubble_relayout_requested', {})
    }

    if (
      (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map') &&
      updates.style &&
      isSessionMindMapV2VisualDesignActive(ctx.mindMapCanvasMode.value) &&
      (updates.style.textAlign !== undefined ||
        updates.style.textDecoration !== undefined ||
        updates.style.fontSize !== undefined ||
        updates.style.fontWeight !== undefined ||
        updates.style.fontStyle !== undefined ||
        updates.style.fontFamily !== undefined ||
        updates.style.textColor !== undefined ||
        updates.style.nodeShape !== undefined)
    ) {
      // Shape or typography changes alter the measured box. Refresh estimates so the
      // layout pass uses the new size before ResizeObserver reports DOM dimensions.
      const typographyChanged =
        updates.style.fontSize !== undefined ||
        updates.style.fontWeight !== undefined ||
        updates.style.fontFamily !== undefined
      const shapeChanged = updates.style.nodeShape !== undefined

      if (typographyChanged || shapeChanged) {
        const refreshed = ctx.data.value.nodes[nodeIndex]
        const text = refreshed.text ?? ''
        const mergedStyle = refreshed.style

        if (nodeId === 'topic') {
          ctx.data.value.nodes[nodeIndex] = {
            ...refreshed,
            data: {
              ...refreshed.data,
              estimatedWidth: estimateTopicNodeWidth(text, mergedStyle),
              estimatedHeight: estimateTopicNodeHeight(text, mergedStyle),
            },
          }
        } else {
          const numberMap = mindMapBranchNumberMapFromData(ctx.data.value)
          const prefix = numberMap.get(nodeId) ?? ''
          const newShape = resolveNodeShape(mergedStyle, true)
          const freshHeight =
            newShape === 'underline'
              ? measureNumberedBranchUnderlineHeight(text, prefix, nodeId, mergedStyle)
              : measureNumberedBranchHeight(text, prefix, nodeId, mergedStyle)
          ctx.data.value.nodes[nodeIndex] = {
            ...refreshed,
            data: {
              ...refreshed.data,
              estimatedWidth: estimateNumberedBranchWidth(text, prefix, nodeId, mergedStyle),
              estimatedHeight: freshHeight,
            },
          }
        }
      }
      delete ctx.nodeDimensions.value[nodeId]
      delete ctx.mindMapNodeWidths.value[nodeId]
      delete ctx.mindMapNodeHeights.value[nodeId]
      if (nodeId === 'topic') {
        ctx.mindMapTopicActualWidth.value = null
      }
      if (shapeChanged) {
        // Mirror 导图样式 switch: shape regime change must full-restack with
        // adaptive gaps (do not keep sticky L1 Enter preserve).
        ctx.mindMapPreserveIncomingY.value = false
        ctx.mindMapPreserveIncomingYNodeId.value = null
      }
      ctx.scheduleMindMapRecalc()
    }

    emitCtxEvent(ctx, 'diagram:node_updated', { nodeId, updates })
    return true
  }

  function emptyNode(nodeId: string): boolean {
    if (!ctx.data.value?.nodes) return false

    const nodeIndex = ctx.data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    ctx.data.value.nodes[nodeIndex] = {
      ...ctx.data.value.nodes[nodeIndex],
      text: '',
    }

    if (ctx.type.value === 'concept_map' && nodeId === 'topic') {
      ;(ctx.data.value as Record<string, unknown>).focus_question = ''
    }

    if (ctx.type.value && shouldInvalidateNodeDimensionsOnTextEdit(ctx.type.value, nodeId)) {
      delete ctx.nodeDimensions.value[nodeId]
    }

    if ((ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map') && nodeId !== 'topic') {
      const freshWidth = estimateMindMapBranchWidth('')
      const freshHeight = measureMindMapBranchHeight('')
      ctx.data.value.nodes[nodeIndex] = {
        ...ctx.data.value.nodes[nodeIndex],
        data: {
          ...ctx.data.value.nodes[nodeIndex].data,
          estimatedWidth: freshWidth,
          estimatedHeight: freshHeight,
        },
      }
    }

    emitCtxEvent(ctx, 'diagram:node_updated', { nodeId, updates: { text: '' } })
    return true
  }

  function addNode(node: DiagramNode): void {
    if (isDiagramPresentationReadOnly(ctx)) return
    if (ctx.collabSessionActive.value && node.id) {
      const suffix = safeRandomUUID().slice(0, 8)
      node.id = `${node.id}-c${suffix}`
    }
    if (!ctx.data.value) {
      ctx.data.value = { type: ctx.type.value || 'mindmap', nodes: [], connections: [] }
    }

    if (ctx.type.value === 'multi_flow_map') {
      const category = (node as unknown as { category?: string }).category
      const selected = ctx.data.value.nodes.find((n) => n.id === ctx.selectedNodes.value[0])
      const selectedRole = selected ? readMultiFlowRole(selected) : null
      const isCause = category === 'causes' || readMultiFlowRole(node) === 'cause'
      const isEffect = category === 'effects' || readMultiFlowRole(node) === 'effect'

      let targetCategory: 'causes' | 'effects' | null = null
      if (!category && selectedRole === 'cause') {
        targetCategory = 'causes'
      } else if (!category && selectedRole === 'effect') {
        targetCategory = 'effects'
      }

      if (!node.text) {
        const t = i18n.global.t
        if (isCause || targetCategory === 'causes') {
          node.text = String(t('diagram.flow.newCause'))
        } else if (isEffect || targetCategory === 'effects') {
          node.text = String(t('diagram.flow.newEffect'))
        } else {
          node.text = String(t('diagram.flow.newCause'))
        }
      }

      const role = isCause || targetCategory === 'causes' ? 'cause' : 'effect'
      const claimed = new Set(ctx.data.value.nodes.map((n) => n.id).filter(Boolean))
      claimed.add(MULTI_FLOW_EVENT_NODE_ID)
      const nextId = takeMultiFlowMapStableId(claimed, node.id)
      const groupIndex = ctx.data.value.nodes.filter((n) =>
        role === 'cause' ? isMultiFlowCauseNode(n) : isMultiFlowEffectNode(n)
      ).length
      ctx.data.value.nodes.push({
        ...node,
        id: nextId,
        type: 'flow',
        data: stampMultiFlowData(role, groupIndex, {
          ...node.data,
          [MULTI_FLOW_UID_DATA_KEY]: nextId,
        }),
      })

      const recalculatedNodes = recalculateMultiFlowMapLayout(
        ctx.data.value.nodes,
        null,
        {},
        ctx.nodeDimensions.value
      )
      const recalculatedConnections: Connection[] = []
      const causeNodes = recalculatedNodes.filter((n) => isMultiFlowCauseNode(n))
      const effectNodes = recalculatedNodes.filter((n) => isMultiFlowEffectNode(n))

      causeNodes.forEach((causeNode, causeIndex) => {
        recalculatedConnections.push({
          id: `edge-${causeNode.id}-${MULTI_FLOW_EVENT_NODE_ID}`,
          source: causeNode.id,
          target: MULTI_FLOW_EVENT_NODE_ID,
          sourceHandle: 'right',
          targetHandle: `left-${causeIndex}`,
          style: { strokeColor: getMindmapBranchColor(causeIndex).border },
        })
      })

      effectNodes.forEach((effectNode, effectIndex) => {
        recalculatedConnections.push({
          id: `edge-${MULTI_FLOW_EVENT_NODE_ID}-${effectNode.id}`,
          source: MULTI_FLOW_EVENT_NODE_ID,
          target: effectNode.id,
          sourceHandle: `right-${effectIndex}`,
          targetHandle: 'left',
          style: { strokeColor: getMindmapBranchColor(effectIndex).border },
        })
      })

      ctx.data.value.nodes = recalculatedNodes
      ctx.data.value.connections = recalculatedConnections
    } else if (ctx.type.value === 'circle_map' && isCircleMapContextNode(node)) {
      const claimed = new Set(ctx.data.value.nodes.map((n) => n.id).filter(Boolean))
      claimed.add(CIRCLE_TOPIC_NODE_ID)
      claimed.add(CIRCLE_BOUNDARY_NODE_ID)
      const nextId = takeCircleMapStableId(claimed, node.id)
      const groupIndex = ctx.data.value.nodes.filter((n) => isCircleMapContextNode(n)).length
      ctx.data.value.nodes.push({
        ...node,
        id: nextId,
        type: 'bubble',
        data: stampCircleContextData(groupIndex, {
          ...node.data,
          [CIRCLE_MAP_UID_DATA_KEY]: nextId,
        }),
      })
      ctx.data.value.nodes = recalculateCircleMapLayout(
        ctx.data.value.nodes,
        ctx.nodeDimensions.value
      )
    } else if (ctx.type.value === 'bridge_map' && isBridgeMapPairNode(node)) {
      const claimed = new Set(ctx.data.value.nodes.map((n) => n.id).filter(Boolean))
      const nextId = takeBridgeMapStableId(claimed, node.id)
      const pairIndex = typeof node.data?.pairIndex === 'number' ? node.data.pairIndex : 0
      const side: BridgePairSide = node.data?.position === 'right' ? 'right' : 'left'
      ctx.data.value.nodes.push({
        ...node,
        id: nextId,
        data: {
          ...stampBridgePairData(pairIndex, side, node.data),
          [BRIDGE_MAP_UID_DATA_KEY]: nextId,
        },
      })
    } else if (ctx.type.value === 'bubble_map' && isBubbleMapAttributeNode(node)) {
      const claimed = new Set(ctx.data.value.nodes.map((n) => n.id).filter(Boolean))
      claimed.add(BUBBLE_TOPIC_NODE_ID)
      const nextId = takeBubbleMapStableId(claimed, node.id)
      const groupIndex = ctx.data.value.nodes.filter((n) => isBubbleMapAttributeNode(n)).length
      ctx.data.value.nodes.push({
        ...node,
        id: nextId,
        data: stampBubbleAttributeData(groupIndex, {
          ...node.data,
          [BUBBLE_MAP_UID_DATA_KEY]: nextId,
        }),
      })
      const recalculatedNodes = recalculateBubbleMapLayout(
        ctx.data.value.nodes,
        ctx.nodeDimensions.value
      )
      const bubbleNodes = recalculatedNodes.filter((n) => isBubbleMapAttributeNode(n))
      ctx.data.value.nodes = recalculatedNodes
      ctx.data.value.connections = bubbleNodes.map((bubbleNode, i) => ({
        id: `edge-${BUBBLE_TOPIC_NODE_ID}-${bubbleNode.id}`,
        source: BUBBLE_TOPIC_NODE_ID,
        target: bubbleNode.id,
        style: { strokeColor: getMindmapBranchColor(i).border },
      }))
    } else if (ctx.type.value === 'concept_map') {
      const conceptNode: DiagramNode = {
        ...node,
        id: node.id || `concept-${Date.now()}-${ctx.data.value.nodes.length}`,
        type: node.type === 'topic' || node.type === 'center' ? node.type : 'branch',
        text: node.text || '????',
      }
      ctx.data.value.nodes.push(conceptNode)
      emitCtxEvent(ctx, 'diagram:node_added', { node: conceptNode })
      return
    } else {
      ctx.data.value.nodes.push(node)
    }

    emitCtxEvent(ctx, 'diagram:node_added', { node })
  }

  function removeNode(nodeId: string): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (!ctx.data.value?.nodes) return false

    if (collabForeignLockBlocksAnyId(ctx, [nodeId])) {
      emitCollabDeleteBlocked()
      return false
    }

    const index = ctx.data.value.nodes.findIndex((n) => n.id === nodeId)
    if (index === -1) return false

    const node = ctx.data.value.nodes[index]

    if (node.type === 'topic' || node.type === 'center') {
      console.warn('Main topic/center node cannot be deleted')
      return false
    }

    if (ctx.type.value === 'multi_flow_map') {
      ctx.setNodeWidth(nodeId, null)

      ctx.data.value.nodes.splice(index, 1)

      const oldCauseNodes = ctx.data.value.nodes.filter((n) => isMultiFlowCauseNode(n))
      const oldEffectNodes = ctx.data.value.nodes.filter((n) => isMultiFlowEffectNode(n))

      const newNodeWidths: Record<string, number> = {}
      oldCauseNodes.forEach((oldNode) => {
        const oldWidth = ctx.nodeWidths.value[oldNode.id]
        if (oldWidth) {
          newNodeWidths[oldNode.id] = oldWidth
        }
      })
      oldEffectNodes.forEach((oldNode) => {
        const oldWidth = ctx.nodeWidths.value[oldNode.id]
        if (oldWidth) {
          newNodeWidths[oldNode.id] = oldWidth
        }
      })

      ctx.nodeWidths.value = newNodeWidths

      const recalculatedNodes = recalculateMultiFlowMapLayout(
        ctx.data.value.nodes,
        ctx.topicNodeWidth.value,
        ctx.nodeWidths.value,
        ctx.nodeDimensions.value
      )
      const recalculatedConnections: Connection[] = []
      const causeNodes = recalculatedNodes.filter((n) => isMultiFlowCauseNode(n))
      const effectNodes = recalculatedNodes.filter((n) => isMultiFlowEffectNode(n))

      causeNodes.forEach((causeNode, causeIndex) => {
        recalculatedConnections.push({
          id: `edge-${causeNode.id}-${MULTI_FLOW_EVENT_NODE_ID}`,
          source: causeNode.id,
          target: MULTI_FLOW_EVENT_NODE_ID,
          sourceHandle: 'right',
          targetHandle: `left-${causeIndex}`,
          style: { strokeColor: getMindmapBranchColor(causeIndex).border },
        })
      })

      effectNodes.forEach((effectNode, effectIndex) => {
        recalculatedConnections.push({
          id: `edge-${MULTI_FLOW_EVENT_NODE_ID}-${effectNode.id}`,
          source: MULTI_FLOW_EVENT_NODE_ID,
          target: effectNode.id,
          sourceHandle: `right-${effectIndex}`,
          targetHandle: 'left',
          style: { strokeColor: getMindmapBranchColor(effectIndex).border },
        })
      })

      ctx.data.value.nodes = recalculatedNodes
      ctx.data.value.connections = recalculatedConnections
      if (ctx.emitDiagramEvents && !ctx.isReadonly.value) {
        useConceptMapRelationshipStore().clearAll()
      }

      ctx.multiFlowMapRecalcTrigger.value++
    } else if (ctx.type.value === 'flow_map') {
      const idsToRemove = new Set<string>([nodeId])
      if (isFlowMapStepNode(node)) {
        ctx.data.value.nodes
          .filter((n) => isFlowMapSubstepNode(n) && flowMapChildBelongsToStep(n, node))
          .forEach((n) => {
            if (n.id) idsToRemove.add(n.id)
          })
      }
      ctx.data.value.nodes = ctx.data.value.nodes.filter((n) => !idsToRemove.has(n.id ?? ''))
      ctx.data.value.connections = (ctx.data.value.connections ?? []).filter(
        (c) => !idsToRemove.has(c.source) && !idsToRemove.has(c.target)
      )
      idsToRemove.forEach((id) => {
        ctx.clearCustomPosition(id)
        ctx.clearNodeStyle(id)
        ctx.removeFromSelection(id)
      })
      const spec = ctx.buildFlowMapSpecFromNodes()
      if (spec) {
        ctx.loadFromSpec(spec, 'flow_map', { mergePreviousNodeStyles: true })
      }
      emitCtxEvent(ctx, 'diagram:nodes_deleted', { nodeIds: [...idsToRemove] })
      return true
    } else if (ctx.type.value === 'bubble_map' && isBubbleMapAttributeNode(node)) {
      ctx.data.value.nodes.splice(index, 1)

      const bubbleNodes = ctx.data.value.nodes.filter((n) => isBubbleMapAttributeNode(n))
      bubbleNodes.forEach((bubbleNode, i) => {
        bubbleNode.data = stampBubbleAttributeData(i, {
          ...bubbleNode.data,
          [BUBBLE_MAP_UID_DATA_KEY]: bubbleNode.id,
        })
      })
      ctx.data.value.connections = bubbleNodes.map((bubbleNode, i) => ({
        id: `edge-${BUBBLE_TOPIC_NODE_ID}-${bubbleNode.id}`,
        source: BUBBLE_TOPIC_NODE_ID,
        target: bubbleNode.id,
        style: { strokeColor: getMindmapBranchColor(i).border },
      }))
      if (ctx.emitDiagramEvents && !ctx.isReadonly.value) {
        useConceptMapRelationshipStore().clearAll()
      }
    } else {
      if (ctx.data.value.connections) {
        const removedConnIds = ctx.data.value.connections
          .filter((c) => c.source === nodeId || c.target === nodeId)
          .map((c) => c.id)
          .filter((id): id is string => !!id)
        ctx.data.value.connections = ctx.data.value.connections.filter(
          (c) => c.source !== nodeId && c.target !== nodeId
        )
        if (ctx.emitDiagramEvents && !ctx.isReadonly.value) {
          const relStore = useConceptMapRelationshipStore()
          removedConnIds.forEach((id) => relStore.clearConnection(id))
        }
      }
      ctx.data.value.nodes.splice(index, 1)
    }

    ctx.clearCustomPosition(nodeId)
    ctx.clearNodeStyle(nodeId)
    ctx.removeFromSelection(nodeId)

    emitCtxEvent(ctx, 'diagram:nodes_deleted', { nodeIds: [nodeId] })
    return true
  }

  return {
    addNode,
    updateNode,
    emptyNode,
    removeNode,
  }
}
