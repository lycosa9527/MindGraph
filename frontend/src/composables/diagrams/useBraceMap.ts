/**
 * useBraceMap - Composable for Brace Map layout and data management
 * Brace maps show part-whole relationships with braces
 *
 * Uses Dagre for automatic layout (LR direction):
 * - Whole on the left
 * - Parts expand to the right with curly brace connectors
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import {
  DEFAULT_LEVEL_WIDTH,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  DEFAULT_VERTICAL_SPACING,
} from './layoutConfig'
import { calculateDagreLayout, type DagreEdgeInput, type DagreNodeInput } from './useDagreLayout'

interface BraceNode {
  id: string
  text: string
  parts?: BraceNode[]
}

interface BraceMapData {
  whole: BraceNode
}

interface BraceMapOptions {
  levelWidth?: number // Horizontal spacing between levels (rankSeparation)
  nodeSpacing?: number // Vertical spacing between siblings (nodeSeparation)
  nodeWidth?: number
  nodeHeight?: number
}

// Helper to flatten brace tree for Dagre
interface FlattenedBraceNode {
  id: string
  text: string
  depth: number
}

export function useBraceMap(options: BraceMapOptions = {}) {
  const {
    levelWidth = DEFAULT_LEVEL_WIDTH,
    nodeSpacing = DEFAULT_VERTICAL_SPACING,
    nodeWidth = DEFAULT_NODE_WIDTH,
    nodeHeight = DEFAULT_NODE_HEIGHT,
  } = options

  const { t } = useLanguage()
  const data = ref<BraceMapData | null>(null)

  // Flatten brace tree into nodes and edges for Dagre
  function flattenBraceTree(
    node: BraceNode,
    depth: number,
    parentId: string | null,
    dagreNodes: DagreNodeInput[],
    dagreEdges: DagreEdgeInput[],
    nodeInfos: Map<string, FlattenedBraceNode>,
    counter: { value: number }
  ): void {
    const nodeId = node.id || `brace-${depth}-${counter.value++}`

    dagreNodes.push({ id: nodeId, width: nodeWidth, height: nodeHeight })
    nodeInfos.set(nodeId, { id: nodeId, text: node.text, depth })

    if (parentId) {
      dagreEdges.push({ source: parentId, target: nodeId })
    }

    if (node.parts && node.parts.length > 0) {
      node.parts.forEach((part) => {
        flattenBraceTree(part, depth + 1, nodeId, dagreNodes, dagreEdges, nodeInfos, counter)
      })
    }
  }

  // Generate layout using Dagre
  function generateLayout(): { nodes: MindGraphNode[]; edges: MindGraphEdge[] } {
    if (!data.value) return { nodes: [], edges: [] }

    const nodes: MindGraphNode[] = []
    const edges: MindGraphEdge[] = []

    const dagreNodes: DagreNodeInput[] = []
    const dagreEdges: DagreEdgeInput[] = []
    const nodeInfos = new Map<string, FlattenedBraceNode>()

    // Flatten the tree structure
    flattenBraceTree(data.value.whole, 0, null, dagreNodes, dagreEdges, nodeInfos, { value: 0 })

    // Calculate layout using Dagre (left-to-right direction for brace maps)
    const layoutResult = calculateDagreLayout(dagreNodes, dagreEdges, {
      direction: 'LR',
      nodeSeparation: nodeSpacing,
      rankSeparation: levelWidth,
      align: 'UL',
      marginX: DEFAULT_PADDING,
      marginY: DEFAULT_PADDING,
    })

    // Build parent-child map from edges
    const childrenMap = new Map<string, string[]>()
    dagreEdges.forEach((edge) => {
      if (!childrenMap.has(edge.source)) {
        childrenMap.set(edge.source, [])
      }
      childrenMap.get(edge.source)!.push(edge.target)
    })

    // Calculate adjusted Y positions by centering each parent relative to its children
    // Process from deepest level to shallowest (bottom-up)
    const adjustedY = new Map<string, number>()
    const maxDepth = Math.max(
      ...Array.from(nodeInfos.values()).map((info) => info.depth)
    )

    // Initialize with original positions
    dagreNodes.forEach((node) => {
      const pos = layoutResult.positions.get(node.id)
      if (pos) {
        adjustedY.set(node.id, pos.y)
      }
    })

    // Process each depth level from bottom to top
    for (let depth = maxDepth; depth >= 0; depth--) {
      dagreNodes.forEach((node) => {
        const info = nodeInfos.get(node.id)
        if (info?.depth === depth) {
          const directChildren = childrenMap.get(node.id) || []
          if (directChildren.length > 0) {
            // Calculate vertical center of direct children
            let minY = Infinity
            let maxY = -Infinity
            directChildren.forEach((childId) => {
              const childY = adjustedY.get(childId)
              if (childY !== undefined) {
                const childTop = childY
                const childBottom = childY + nodeHeight
                if (childTop < minY) minY = childTop
                if (childBottom > maxY) maxY = childBottom
              }
            })
            if (minY !== Infinity && maxY !== -Infinity) {
              const childrenCenterY = (minY + maxY) / 2
              adjustedY.set(node.id, childrenCenterY - nodeHeight / 2)
            }
          }
        }
      })
    }

    // Create VueFlow nodes with adjusted positions
    dagreNodes.forEach((dagreNode) => {
      const info = nodeInfos.get(dagreNode.id)
      const pos = layoutResult.positions.get(dagreNode.id)
      const adjustedPosY = adjustedY.get(dagreNode.id)

      if (info && pos) {
        nodes.push({
          id: dagreNode.id,
          type: info.depth === 0 ? 'topic' : 'brace',
          position: { x: pos.x, y: adjustedPosY !== undefined ? adjustedPosY : pos.y },
          data: {
            label: info.text,
            nodeType: info.depth === 0 ? 'topic' : 'brace',
            diagramType: 'brace_map',
            isDraggable: info.depth > 0,
            isSelectable: true,
          },
          draggable: info.depth > 0,
        })
      }
    })

    // Create edges
    dagreEdges.forEach((edge) => {
      edges.push({
        id: `edge-${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        type: 'brace',
        data: { edgeType: 'brace' as const },
      })
    })

    return { nodes, edges }
  }

  // Convert brace map data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    return generateLayout().nodes
  })

  // Generate edges
  const edges = computed<MindGraphEdge[]>(() => {
    return generateLayout().edges
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
