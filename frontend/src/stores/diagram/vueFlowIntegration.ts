import { computed } from 'vue'

import {
  augmentConnectionWithOptimalHandles,
  splitMixedArrowHandleGroups,
} from '@/composables/diagrams/conceptMapHandles'
import type { Connection, MindGraphEdge, MindGraphEdgeType, MindGraphNode } from '@/types'
import {
  connectionToVueFlowEdge,
  diagramNodeToVueFlowNode,
  vueFlowNodeToDiagramNode,
} from '@/types/vueflow'

import {
  recalculateBraceMapLayout,
  recalculateBubbleMapLayout,
  recalculateCircleMapLayout,
  recalculateMultiFlowMapLayout,
} from '../specLoader'
import { getEdgeTypeForDiagram } from './events'
import { recalculateMindMapColumnPositions } from './mindMapLayout'
import type { DiagramContext } from './types'

export function useVueFlowIntegrationSlice(ctx: DiagramContext) {
  const circleMapLayoutNodes = computed(() => {
    if (ctx.type.value !== 'circle_map' || !ctx.data.value?.nodes) return []
    return recalculateCircleMapLayout(ctx.data.value.nodes)
  })

  const vueFlowNodes = computed<MindGraphNode[]>(() => {
    const diagramType = ctx.type.value
    if (!ctx.data.value?.nodes || !diagramType) return []

    if (diagramType === 'circle_map') {
      const layoutNodes = circleMapLayoutNodes.value
      return layoutNodes.map((node) => {
        const vf = diagramNodeToVueFlowNode(node, diagramType)
        vf.selected = ctx.selectedNodes.value.includes(node.id)
        vf.draggable = false
        return vf
      })
    }

    if (diagramType === 'multi_flow_map') {
      void ctx.multiFlowMapRecalcTrigger.value

      const recalculatedNodes = recalculateMultiFlowMapLayout(
        ctx.data.value.nodes,
        ctx.topicNodeWidth.value,
        ctx.nodeWidths.value
      )
      const causeNodes = recalculatedNodes.filter((n) => n.id.startsWith('cause-'))
      const effectNodes = recalculatedNodes.filter((n) => n.id.startsWith('effect-'))

      return recalculatedNodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = ctx.selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        if (node.id === 'event' && vueFlowNode.data) {
          vueFlowNode.data.causeCount = causeNodes.length
          vueFlowNode.data.effectCount = effectNodes.length
        }
        if ((node.id.startsWith('cause-') || node.id.startsWith('effect-')) && node.style) {
          vueFlowNode.style = {
            ...vueFlowNode.style,
            width: node.style.width,
            minWidth: node.style.width,
          }
        }
        return vueFlowNode
      })
    }

    if (diagramType === 'mindmap' || diagramType === 'mind_map') {
      void ctx.mindMapRecalcTrigger.value

      const connections = ctx.data.value.connections ?? []
      const { nodes: correctedNodes, gaps } = recalculateMindMapColumnPositions(
        ctx.data.value.nodes,
        ctx.mindMapTopicActualWidth.value,
        ctx.mindMapNodeWidths.value,
        ctx.mindMapNodeHeights.value,
        connections
      )
      ctx.mindMapTopicBranchGaps.value = gaps
      const firstLevelBranchCount = connections.filter((c) => c.source === 'topic').length

      return correctedNodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = ctx.selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        if (node.id === 'topic' && vueFlowNode.data) {
          vueFlowNode.data.totalBranchCount = firstLevelBranchCount
        }
        return vueFlowNode
      })
    }

    if (diagramType === 'bubble_map') {
      const layoutNodes = recalculateBubbleMapLayout(ctx.data.value.nodes)
      return layoutNodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = ctx.selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        return vueFlowNode
      })
    }

    if (diagramType === 'double_bubble_map') {
      return ctx.data.value.nodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = ctx.selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        return vueFlowNode
      })
    }

    if (diagramType === 'flow_map') {
      return ctx.data.value.nodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = ctx.selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        return vueFlowNode
      })
    }

    if (diagramType === 'brace_map') {
      const layoutNodes = recalculateBraceMapLayout(
        ctx.data.value.nodes,
        ctx.data.value.connections ?? []
      )
      return layoutNodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = ctx.selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        return vueFlowNode
      })
    }

    if (diagramType === 'tree_map') {
      return ctx.data.value.nodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = ctx.selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        return vueFlowNode
      })
    }

    const disableDrag = diagramType !== 'concept_map'
    return ctx.data.value.nodes.map((node) => {
      const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
      vueFlowNode.selected = ctx.selectedNodes.value.includes(node.id)
      if (disableDrag) vueFlowNode.draggable = false
      return vueFlowNode
    })
  })

  const vueFlowEdges = computed<MindGraphEdge[]>(() => {
    if (ctx.type.value === 'circle_map') return []

    if (!ctx.data.value?.connections) return []
    const defaultEdgeType = getEdgeTypeForDiagram(ctx.type.value)
    const diagramType = ctx.type.value
    const nodes = ctx.data.value.nodes ?? []

    const edges = ctx.data.value.connections.map((conn) => {
      const effectiveConn =
        diagramType === 'concept_map' ? augmentConnectionWithOptimalHandles(conn, nodes) : conn

      const edgeType = (effectiveConn.edgeType as MindGraphEdgeType) || defaultEdgeType
      const edge = connectionToVueFlowEdge(effectiveConn, edgeType)
      if (diagramType && edge.data) {
        edge.data = { ...edge.data, diagramType }
      }
      return edge
    })

    if (diagramType === 'concept_map' && edges.length > 0) {
      splitMixedArrowHandleGroups(edges, nodes)

      const targetGroups = new Map<string, MindGraphEdge[]>()
      for (const edge of edges) {
        const key = `${edge.target}:${edge.targetHandle ?? ''}`
        if (!targetGroups.has(key)) targetGroups.set(key, [])
        const tg = targetGroups.get(key)
        if (tg) {
          tg.push(edge)
        }
      }
      for (const group of targetGroups.values()) {
        const allHaveTarget = group.every(
          (e) => e.data?.arrowheadDirection === 'target' || e.data?.arrowheadDirection === 'both'
        )
        group.forEach((edge, i) => {
          if (!edge.data) return
          if (allHaveTarget) {
            edge.data = { ...edge.data, drawTargetArrowhead: i === 0 }
          } else {
            const hasTarget =
              edge.data.arrowheadDirection === 'target' || edge.data.arrowheadDirection === 'both'
            edge.data = { ...edge.data, drawTargetArrowhead: hasTarget }
          }
        })
      }

      const sourceGroups = new Map<string, MindGraphEdge[]>()
      for (const edge of edges) {
        const key = `${edge.source}:${edge.sourceHandle ?? ''}`
        if (!sourceGroups.has(key)) sourceGroups.set(key, [])
        const sg = sourceGroups.get(key)
        if (sg) {
          sg.push(edge)
        }
      }
      for (const group of sourceGroups.values()) {
        const allHaveSource = group.every(
          (e) => e.data?.arrowheadDirection === 'source' || e.data?.arrowheadDirection === 'both'
        )
        group.forEach((edge, i) => {
          if (!edge.data) return
          if (allHaveSource) {
            edge.data = { ...edge.data, drawSourceArrowhead: i === 0 }
          } else {
            const hasSource =
              edge.data.arrowheadDirection === 'source' || edge.data.arrowheadDirection === 'both'
            edge.data = { ...edge.data, drawSourceArrowhead: hasSource }
          }
        })
      }
    }

    return edges
  })

  function updateNodePosition(
    nodeId: string,
    position: { x: number; y: number },
    isUserDrag: boolean = false
  ): boolean {
    if (!ctx.data.value?.nodes) return false

    const nodeIndex = ctx.data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    ctx.data.value.nodes[nodeIndex] = {
      ...ctx.data.value.nodes[nodeIndex],
      position: { x: position.x, y: position.y },
    }

    if (isUserDrag) {
      ctx.saveCustomPosition(nodeId, position.x, position.y)
    }

    return true
  }

  function updateNodesFromVueFlow(vfNodes: MindGraphNode[]): void {
    const diagramData = ctx.data.value
    if (!diagramData) return

    vfNodes.forEach((vfNode) => {
      const nodeIndex = diagramData.nodes.findIndex((n) => n.id === vfNode.id)
      if (nodeIndex !== -1 && vfNode.data) {
        diagramData.nodes[nodeIndex] = {
          ...diagramData.nodes[nodeIndex],
          position: { x: vfNode.position.x, y: vfNode.position.y },
          text: vfNode.data.label,
        }
      }
    })
  }

  function syncFromVueFlow(nodes: MindGraphNode[], edges: MindGraphEdge[]): void {
    if (!ctx.data.value) {
      ctx.data.value = { type: ctx.type.value || 'mindmap', nodes: [], connections: [] }
    }

    ctx.data.value.nodes = nodes.map((vfNode) => vueFlowNodeToDiagramNode(vfNode))

    ctx.data.value.connections = edges.map((edge) => {
      const existing = ctx.data.value?.connections?.find((c) => c.id === edge.id)
      const conn: Connection = {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.data?.label,
        style: edge.data?.style,
        sourceHandle: edge.sourceHandle ?? undefined,
        targetHandle: edge.targetHandle ?? undefined,
        sourcePosition: edge.sourcePosition,
        targetPosition: edge.targetPosition,
        arrowheadDirection: ((): Connection['arrowheadDirection'] => {
          const d = edge.data?.arrowheadDirection ?? existing?.arrowheadDirection
          return d === 'source' || d === 'target' || d === 'both' ? d : undefined
        })(),
      }
      return conn
    })
  }

  return {
    circleMapLayoutNodes,
    vueFlowNodes,
    vueFlowEdges,
    updateNodePosition,
    updateNodesFromVueFlow,
    syncFromVueFlow,
  }
}
