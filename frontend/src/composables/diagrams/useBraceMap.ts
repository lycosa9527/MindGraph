/**
 * useBraceMap - Composable for Brace Map layout and data management
 * Brace maps show part-whole relationships with braces
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import {
  DEFAULT_CENTER_Y,
  DEFAULT_LEVEL_WIDTH,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_PADDING,
  DEFAULT_VERTICAL_SPACING,
} from './layoutConfig'

interface BraceNode {
  id: string
  text: string
  parts?: BraceNode[]
}

interface BraceMapData {
  whole: BraceNode
}

interface BraceMapOptions {
  startX?: number
  centerY?: number
  levelWidth?: number
  nodeSpacing?: number
  nodeWidth?: number
  nodeHeight?: number
}

interface LayoutResult {
  nodes: MindGraphNode[]
  edges: MindGraphEdge[]
  height: number
  topY: number
  bottomY: number
}

export function useBraceMap(options: BraceMapOptions = {}) {
  const {
    startX = DEFAULT_PADDING + 60, // 100px
    centerY = DEFAULT_CENTER_Y,
    levelWidth = DEFAULT_LEVEL_WIDTH,
    nodeSpacing = DEFAULT_VERTICAL_SPACING, // 60px
    nodeWidth: _nodeWidth = 140,
    nodeHeight = DEFAULT_NODE_HEIGHT,
  } = options
  // nodeWidth reserved for future use
  void _nodeWidth

  const { t } = useLanguage()
  const data = ref<BraceMapData | null>(null)

  // Calculate total height for a node and its parts
  function calculateHeight(node: BraceNode): number {
    if (!node.parts || node.parts.length === 0) {
      return nodeHeight
    }

    return node.parts.reduce((sum, part) => {
      return sum + calculateHeight(part) + nodeSpacing
    }, -nodeSpacing)
  }

  // Layout nodes recursively from left to right with braces
  function layoutNode(
    node: BraceNode,
    x: number,
    centerYPos: number,
    depth: number,
    parentId?: string
  ): LayoutResult {
    const result: LayoutResult = {
      nodes: [],
      edges: [],
      height: nodeHeight,
      topY: centerYPos - nodeHeight / 2,
      bottomY: centerYPos + nodeHeight / 2,
    }

    const nodeId = node.id || `brace-${depth}-${Date.now()}`

    // Create node
    const vueFlowNode: MindGraphNode = {
      id: nodeId,
      type: depth === 0 ? 'topic' : 'brace',
      position: { x, y: centerYPos - nodeHeight / 2 },
      data: {
        label: node.text,
        nodeType: depth === 0 ? 'topic' : 'brace',
        diagramType: 'brace_map',
        isDraggable: depth > 0,
        isSelectable: true,
      },
      draggable: depth > 0,
    }
    result.nodes.push(vueFlowNode)

    // Create brace edge to parent
    if (parentId) {
      result.edges.push({
        id: `edge-${parentId}-${nodeId}`,
        source: parentId,
        target: nodeId,
        type: 'brace',
        data: { edgeType: 'brace' as const },
      })
    }

    // Layout parts (children)
    if (node.parts && node.parts.length > 0) {
      const partsHeights = node.parts.map((part) => calculateHeight(part))
      const totalPartsHeight =
        partsHeights.reduce((sum, h) => sum + h, 0) + (node.parts.length - 1) * nodeSpacing

      let partY = centerYPos - totalPartsHeight / 2

      const partResults: LayoutResult[] = []

      node.parts.forEach((part, index) => {
        const partHeight = partsHeights[index]
        const partCenterY = partY + partHeight / 2

        const partResult = layoutNode(part, x + levelWidth, partCenterY, depth + 1, nodeId)
        partResults.push(partResult)
        result.nodes.push(...partResult.nodes)
        result.edges.push(...partResult.edges)

        partY += partHeight + nodeSpacing
      })

      // Update bounds
      if (partResults.length > 0) {
        result.topY = Math.min(result.topY, ...partResults.map((r) => r.topY))
        result.bottomY = Math.max(result.bottomY, ...partResults.map((r) => r.bottomY))
      }
      result.height = result.bottomY - result.topY
    }

    return result
  }

  // Convert brace map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result = layoutNode(data.value.whole, startX, centerY, 0)
    return result.nodes
  })

  // Generate edges
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    const result = layoutNode(data.value.whole, startX, centerY, 0)
    return result.edges
  })

  // Set brace map data
  function setData(newData: BraceMapData) {
    data.value = newData
  }

  // Convert from flat diagram nodes
  function fromDiagramNodes(diagramNodes: DiagramNode[], connections: Connection[]) {
    if (diagramNodes.length === 0) return

    // Find root node (the "whole")
    const targetIds = new Set(connections.map((c) => c.target))
    const rootNode =
      diagramNodes.find(
        (n) => !targetIds.has(n.id) && (n.type === 'topic' || n.type === 'center')
      ) ||
      diagramNodes.find((n) => !targetIds.has(n.id)) ||
      diagramNodes[0]

    // Build hierarchy recursively
    function buildParts(parentId: string): BraceNode[] {
      const childConnections = connections.filter((c) => c.source === parentId)
      const result: BraceNode[] = []
      for (const c of childConnections) {
        const childNode = diagramNodes.find((n) => n.id === c.target)
        if (childNode) {
          const childParts = buildParts(childNode.id)
          result.push({
            id: childNode.id,
            text: childNode.text,
            parts: childParts.length > 0 ? childParts : undefined,
          })
        }
      }
      return result
    }

    data.value = {
      whole: {
        id: rootNode.id,
        text: rootNode.text,
        parts: buildParts(rootNode.id),
      },
    }
  }

  // Add part to a node (requires selection context matching old JS behavior)
  function addPart(parentId: string, text?: string, selectedNodeId?: string): boolean {
    if (!data.value) return false

    // Selection validation - if selectedNodeId is the whole, that's valid
    // Otherwise use selectedNodeId as parentId
    const targetParentId = selectedNodeId || parentId

    // Use default translated text if not provided (matching old JS behavior)
    const partText = text || t('diagram.newPart', 'New Part')

    function findAndAdd(node: BraceNode): boolean {
      if (node.id === targetParentId) {
        if (!node.parts) {
          node.parts = []
        }
        node.parts.push({
          id: `brace-part-${Date.now()}`,
          text: partText,
        })
        return true
      }

      if (node.parts) {
        for (const part of node.parts) {
          if (findAndAdd(part)) return true
        }
      }
      return false
    }

    return findAndAdd(data.value.whole)
  }

  // Remove part by id
  function removePart(partId: string) {
    if (!data.value || data.value.whole.id === partId) return

    function findAndRemove(parent: BraceNode): boolean {
      if (!parent.parts) return false

      const index = parent.parts.findIndex((p) => p.id === partId)
      if (index !== -1) {
        parent.parts.splice(index, 1)
        if (parent.parts.length === 0) {
          parent.parts = undefined
        }
        return true
      }

      for (const part of parent.parts) {
        if (findAndRemove(part)) return true
      }
      return false
    }

    findAndRemove(data.value.whole)
  }

  // Update node text
  function updateText(nodeId: string, text: string) {
    if (!data.value) return

    function findAndUpdate(node: BraceNode): boolean {
      if (node.id === nodeId) {
        node.text = text
        return true
      }

      if (node.parts) {
        for (const part of node.parts) {
          if (findAndUpdate(part)) return true
        }
      }
      return false
    }

    findAndUpdate(data.value.whole)
  }

  return {
    data,
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addPart,
    removePart,
    updateText,
  }
}
