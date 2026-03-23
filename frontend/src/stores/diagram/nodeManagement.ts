import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'

import { useConceptMapRelationshipStore } from '../conceptMapRelationship'
import { recalculateBubbleMapLayout, recalculateMultiFlowMapLayout } from '../specLoader'
import { applyTreeMapTopicLayoutToNodes } from '../specLoader/treeMapTopicLayout'
import { collabForeignLockBlocksAnyId, emitCollabDeleteBlocked } from './collabHelpers'
import { emitEvent } from './events'
import type { DiagramContext } from './types'

export function useNodeManagementSlice(ctx: DiagramContext) {
  function updateNode(nodeId: string, updates: Partial<DiagramNode>): boolean {
    if (!ctx.data.value?.nodes) return false

    const nodeIndex = ctx.data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    const oldNode = ctx.data.value.nodes[nodeIndex]
    const merged: DiagramNode = {
      ...oldNode,
      ...updates,
    }

    if (ctx.type.value === 'tree_map' && nodeId === 'tree-topic' && 'text' in updates) {
      ctx.data.value.nodes = applyTreeMapTopicLayoutToNodes(ctx.data.value.nodes, nodeIndex, merged)
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

    emitEvent('diagram:node_updated', { nodeId, updates })
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

    emitEvent('diagram:node_updated', { nodeId, updates: { text: '' } })
    return true
  }

  function addNode(node: DiagramNode): void {
    if (ctx.collabSessionActive.value && node.id) {
      const suffix =
        typeof crypto !== 'undefined' && crypto.randomUUID
          ? crypto.randomUUID().slice(0, 8)
          : `${Date.now().toString(36)}`
      node.id = `${node.id}-c${suffix}`
    }
    if (!ctx.data.value) {
      ctx.data.value = { type: ctx.type.value || 'mindmap', nodes: [], connections: [] }
    }

    if (ctx.type.value === 'multi_flow_map') {
      const category = (node as unknown as { category?: string }).category
      const isCause = category === 'causes' || node.id?.startsWith('cause-')
      const isEffect = category === 'effects' || node.id?.startsWith('effect-')

      let targetCategory: 'causes' | 'effects' | null = null
      if (!category && ctx.selectedNodes.value.length > 0) {
        const selectedId = ctx.selectedNodes.value[0]
        if (selectedId.startsWith('cause-')) {
          targetCategory = 'causes'
        } else if (selectedId.startsWith('effect-')) {
          targetCategory = 'effects'
        }
      }

      if (!node.text) {
        if (isCause || targetCategory === 'causes') {
          node.text = 'New Cause'
        } else if (isEffect || targetCategory === 'effects') {
          node.text = 'New Effect'
        } else {
          node.text = 'New Cause'
        }
      }

      ctx.data.value.nodes.push(node)

      const recalculatedNodes = recalculateMultiFlowMapLayout(ctx.data.value.nodes)
      const recalculatedConnections: Connection[] = []
      const causeNodes = recalculatedNodes.filter((n) => n.id.startsWith('cause-'))
      const effectNodes = recalculatedNodes.filter((n) => n.id.startsWith('effect-'))

      causeNodes.forEach((causeNode, causeIndex) => {
        recalculatedConnections.push({
          id: `edge-cause-${causeIndex}`,
          source: causeNode.id,
          target: 'event',
          sourceHandle: 'right',
          targetHandle: `left-${causeIndex}`,
          style: { strokeColor: getMindmapBranchColor(causeIndex).border },
        })
      })

      effectNodes.forEach((effectNode, effectIndex) => {
        recalculatedConnections.push({
          id: `edge-effect-${effectIndex}`,
          source: 'event',
          target: effectNode.id,
          sourceHandle: `right-${effectIndex}`,
          targetHandle: 'left',
          style: { strokeColor: getMindmapBranchColor(effectIndex).border },
        })
      })

      ctx.data.value.nodes = recalculatedNodes
      ctx.data.value.connections = recalculatedConnections
    } else if (ctx.type.value === 'bubble_map' && node.id?.startsWith('bubble-')) {
      ctx.data.value.nodes.push(node)
      const recalculatedNodes = recalculateBubbleMapLayout(ctx.data.value.nodes)
      const bubbleNodes = recalculatedNodes.filter(
        (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
      )
      ctx.data.value.nodes = recalculatedNodes
      ctx.data.value.connections = bubbleNodes.map((_, i) => ({
        id: `edge-topic-bubble-${i}`,
        source: 'topic',
        target: `bubble-${i}`,
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
      emitEvent('diagram:node_added', { node: conceptNode })
      return
    } else {
      ctx.data.value.nodes.push(node)
    }

    emitEvent('diagram:node_added', { node })
  }

  function removeNode(nodeId: string): boolean {
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

      const oldCauseNodes = ctx.data.value.nodes
        .filter((n) => n.id.startsWith('cause-'))
        .sort((a, b) => {
          const aIndex = parseInt(a.id.replace('cause-', ''), 10)
          const bIndex = parseInt(b.id.replace('cause-', ''), 10)
          return aIndex - bIndex
        })
      const oldEffectNodes = ctx.data.value.nodes
        .filter((n) => n.id.startsWith('effect-'))
        .sort((a, b) => {
          const aIndex = parseInt(a.id.replace('effect-', ''), 10)
          const bIndex = parseInt(b.id.replace('effect-', ''), 10)
          return aIndex - bIndex
        })

      const newNodeWidths: Record<string, number> = {}
      oldCauseNodes.forEach((oldNode, newIndex) => {
        const oldWidth = ctx.nodeWidths.value[oldNode.id]
        if (oldWidth) {
          newNodeWidths[`cause-${newIndex}`] = oldWidth
        }
      })
      oldEffectNodes.forEach((oldNode, newIndex) => {
        const oldWidth = ctx.nodeWidths.value[oldNode.id]
        if (oldWidth) {
          newNodeWidths[`effect-${newIndex}`] = oldWidth
        }
      })

      ctx.nodeWidths.value = newNodeWidths

      const recalculatedNodes = recalculateMultiFlowMapLayout(
        ctx.data.value.nodes,
        ctx.topicNodeWidth.value,
        ctx.nodeWidths.value
      )
      const recalculatedConnections: Connection[] = []
      const causeNodes = recalculatedNodes.filter((n) => n.id.startsWith('cause-'))
      const effectNodes = recalculatedNodes.filter((n) => n.id.startsWith('effect-'))

      causeNodes.forEach((causeNode, causeIndex) => {
        recalculatedConnections.push({
          id: `edge-cause-${causeIndex}`,
          source: causeNode.id,
          target: 'event',
          sourceHandle: 'right',
          targetHandle: `left-${causeIndex}`,
          style: { strokeColor: getMindmapBranchColor(causeIndex).border },
        })
      })

      effectNodes.forEach((effectNode, effectIndex) => {
        recalculatedConnections.push({
          id: `edge-effect-${effectIndex}`,
          source: 'event',
          target: effectNode.id,
          sourceHandle: `right-${effectIndex}`,
          targetHandle: 'left',
          style: { strokeColor: getMindmapBranchColor(effectIndex).border },
        })
      })

      ctx.data.value.nodes = recalculatedNodes
      ctx.data.value.connections = recalculatedConnections
      useConceptMapRelationshipStore().clearAll()

      ctx.multiFlowMapRecalcTrigger.value++
    } else if (ctx.type.value === 'flow_map') {
      const idsToRemove = new Set<string>([nodeId])
      if (node.type === 'flow') {
        const stepMatch = nodeId.match(/flow-step-(\d+)/)
        if (stepMatch) {
          const stepIndex = stepMatch[1]
          ctx.data.value.nodes
            .filter((n) => n.id?.startsWith(`flow-substep-${stepIndex}-`))
            .forEach((n) => {
              if (n.id) idsToRemove.add(n.id)
            })
        }
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
        ctx.loadFromSpec(spec, 'flow_map')
      }
      emitEvent('diagram:nodes_deleted', { nodeIds: [...idsToRemove] })
      return true
    } else if (ctx.type.value === 'bubble_map' && nodeId.startsWith('bubble-')) {
      ctx.data.value.nodes.splice(index, 1)

      const bubbleNodes = ctx.data.value.nodes.filter(
        (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
      )
      bubbleNodes.forEach((bubbleNode, i) => {
        bubbleNode.id = `bubble-${i}`
      })
      ctx.data.value.connections = bubbleNodes.map((_, i) => ({
        id: `edge-topic-bubble-${i}`,
        source: 'topic',
        target: `bubble-${i}`,
        style: { strokeColor: getMindmapBranchColor(i).border },
      }))
      useConceptMapRelationshipStore().clearAll()
    } else {
      if (ctx.data.value.connections) {
        const removedConnIds = ctx.data.value.connections
          .filter((c) => c.source === nodeId || c.target === nodeId)
          .map((c) => c.id)
          .filter((id): id is string => !!id)
        ctx.data.value.connections = ctx.data.value.connections.filter(
          (c) => c.source !== nodeId && c.target !== nodeId
        )
        const relStore = useConceptMapRelationshipStore()
        removedConnIds.forEach((id) => relStore.clearConnection(id))
      }
      ctx.data.value.nodes.splice(index, 1)
    }

    ctx.clearCustomPosition(nodeId)
    ctx.clearNodeStyle(nodeId)
    ctx.removeFromSelection(nodeId)

    emitEvent('diagram:nodes_deleted', { nodeIds: [nodeId] })
    return true
  }

  return {
    addNode,
    updateNode,
    emptyNode,
    removeNode,
  }
}
