/**
 * useTreeMap - Composable for Tree Map layout and data management
 * Tree maps display hierarchical classification with top-down structure
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import {
  DEFAULT_CENTER_X,
  DEFAULT_LEVEL_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from './layoutConfig'

interface TreeNode {
  id: string
  text: string
  children?: TreeNode[]
}

interface TreeMapData {
  root: TreeNode
  dimension?: string
  alternativeDimensions?: string[]
}

interface TreeMapOptions {
  startX?: number
  startY?: number
  levelHeight?: number
  nodeSpacing?: number
  nodeWidth?: number
  nodeHeight?: number
}

interface LayoutResult {
  nodes: MindGraphNode[]
  edges: MindGraphEdge[]
  width: number
}

export function useTreeMap(options: TreeMapOptions = {}) {
  const {
    startX = DEFAULT_CENTER_X,
    startY = DEFAULT_PADDING + 20, // 60px
    levelHeight = DEFAULT_LEVEL_HEIGHT,
    nodeSpacing = DEFAULT_PADDING,
    nodeWidth = DEFAULT_NODE_WIDTH,
    nodeHeight: _nodeHeight = DEFAULT_PADDING, // 40px
  } = options
  // nodeHeight reserved for future use
  void _nodeHeight

  const { t } = useLanguage()
  const data = ref<TreeMapData | null>(null)

  // Recursively calculate subtree width
  function calculateSubtreeWidth(node: TreeNode): number {
    if (!node.children || node.children.length === 0) {
      return nodeWidth
    }

    const childrenWidth = node.children.reduce((sum, child) => {
      return sum + calculateSubtreeWidth(child) + nodeSpacing
    }, -nodeSpacing)

    return Math.max(nodeWidth, childrenWidth)
  }

  // Recursively layout tree nodes
  function layoutNode(
    node: TreeNode,
    centerX: number,
    y: number,
    depth: number,
    parentId?: string
  ): LayoutResult {
    const result: LayoutResult = { nodes: [], edges: [], width: 0 }

    const nodeId = node.id || `tree-${depth}-${Date.now()}`

    // Create node
    const vueFlowNode: MindGraphNode = {
      id: nodeId,
      type: depth === 0 ? 'topic' : 'branch',
      position: { x: centerX - nodeWidth / 2, y },
      data: {
        label: node.text,
        nodeType: depth === 0 ? 'topic' : 'branch',
        diagramType: 'tree_map',
        isDraggable: depth > 0,
        isSelectable: true,
      },
      draggable: depth > 0,
    }
    result.nodes.push(vueFlowNode)

    // Create edge to parent
    if (parentId) {
      result.edges.push({
        id: `edge-${parentId}-${nodeId}`,
        source: parentId,
        target: nodeId,
        type: 'straight',
        data: { edgeType: 'straight' as const },
      })
    }

    // Layout children
    if (node.children && node.children.length > 0) {
      const childrenWidths = node.children.map((child) => calculateSubtreeWidth(child))
      const totalChildrenWidth =
        childrenWidths.reduce((sum, w) => sum + w, 0) + (node.children.length - 1) * nodeSpacing

      let childX = centerX - totalChildrenWidth / 2

      node.children.forEach((child, index) => {
        const childWidth = childrenWidths[index]
        const childCenterX = childX + childWidth / 2
        const childY = y + levelHeight

        const childResult = layoutNode(child, childCenterX, childY, depth + 1, nodeId)
        result.nodes.push(...childResult.nodes)
        result.edges.push(...childResult.edges)

        childX += childWidth + nodeSpacing
      })
    }

    result.width = calculateSubtreeWidth(node)
    return result
  }

  // Convert tree data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    if (!data.value) return []

    const result = layoutNode(data.value.root, startX, startY, 0)
    const allNodes = [...result.nodes]

    // Add dimension label node below topic if dimension exists
    if (data.value.dimension !== undefined) {
      const dimensionY = startY + 50 // Position below topic
      allNodes.push({
        id: 'dimension-label',
        type: 'label',
        position: { x: startX - 100, y: dimensionY },
        data: {
          label: data.value.dimension || t('diagram.dimensionPlaceholder', 'Classification by: click to specify...'),
          nodeType: 'dimension',
          diagramType: 'tree_map',
          isDraggable: false,
          isSelectable: true,
          isPlaceholder: !data.value.dimension,
        },
        draggable: false,
        selectable: true,
      })
    }

    return allNodes
  })

  // Generate edges
  const edges = computed<MindGraphEdge[]>(() => {
    if (!data.value) return []

    const result = layoutNode(data.value.root, startX, startY, 0)
    return result.edges
  })

  // Set tree map data
  function setData(newData: TreeMapData) {
    data.value = newData
  }

  // Convert from flat diagram nodes
  function fromDiagramNodes(diagramNodes: DiagramNode[], connections: Connection[]) {
    if (diagramNodes.length === 0) return

    // Find root node (no incoming connections)
    const targetIds = new Set(connections.map((c) => c.target))
    const rootNode =
      diagramNodes.find(
        (n) => !targetIds.has(n.id) && (n.type === 'topic' || n.type === 'center')
      ) ||
      diagramNodes.find((n) => !targetIds.has(n.id)) ||
      diagramNodes[0]

    // Build tree recursively
    function buildTree(nodeId: string): TreeNode | null {
      const node = diagramNodes.find((n) => n.id === nodeId)
      if (!node) return null

      const childConnections = connections.filter((c) => c.source === nodeId)
      const children = childConnections
        .map((c) => buildTree(c.target))
        .filter((n): n is TreeNode => n !== null)

      return {
        id: node.id,
        text: node.text,
        children: children.length > 0 ? children : undefined,
      }
    }

    const root = buildTree(rootNode.id)
    if (root) {
      data.value = { root }
    }
  }

  // Add child to a node (requires selection context matching old JS behavior)
  function addChild(parentId: string, text?: string, selectedNodeId?: string): boolean {
    if (!data.value) return false

    // Selection validation - must select a node that's not the root
    if (selectedNodeId && selectedNodeId === data.value.root.id) {
      console.warn('Cannot add children to root node directly')
      return false
    }

    // If selectedNodeId is provided, use it as parentId
    const targetParentId = selectedNodeId || parentId

    // Use default translated text if not provided (matching old JS behavior)
    const childText = text || t('diagram.newChild', 'New Child')

    function findAndAddChild(node: TreeNode): boolean {
      if (node.id === targetParentId) {
        if (!node.children) {
          node.children = []
        }
        node.children.push({
          id: `tree-child-${Date.now()}`,
          text: childText,
        })
        return true
      }

      if (node.children) {
        for (const child of node.children) {
          if (findAndAddChild(child)) return true
        }
      }
      return false
    }

    return findAndAddChild(data.value.root)
  }

  // Remove node by id
  function removeNode(nodeId: string) {
    if (!data.value || data.value.root.id === nodeId) return

    function findAndRemove(parent: TreeNode): boolean {
      if (!parent.children) return false

      const index = parent.children.findIndex((c) => c.id === nodeId)
      if (index !== -1) {
        parent.children.splice(index, 1)
        if (parent.children.length === 0) {
          parent.children = undefined
        }
        return true
      }

      for (const child of parent.children) {
        if (findAndRemove(child)) return true
      }
      return false
    }

    findAndRemove(data.value.root)
  }

  // Update node text
  function updateNodeText(nodeId: string, text: string) {
    if (!data.value) return

    // Handle dimension label updates
    if (nodeId === 'dimension-label') {
      data.value.dimension = text
      return
    }

    function findAndUpdate(node: TreeNode): boolean {
      if (node.id === nodeId) {
        node.text = text
        return true
      }

      if (node.children) {
        for (const child of node.children) {
          if (findAndUpdate(child)) return true
        }
      }
      return false
    }

    findAndUpdate(data.value.root)
  }

  // Update dimension label
  function updateDimension(dimension: string) {
    if (!data.value) return
    data.value.dimension = dimension
  }

  // Set alternative dimensions
  function setAlternativeDimensions(alternatives: string[]) {
    if (!data.value) return
    data.value.alternativeDimensions = alternatives
  }

  return {
    data,
    nodes,
    edges,
    setData,
    fromDiagramNodes,
    addChild,
    removeNode,
    updateNodeText,
    updateDimension,
    setAlternativeDimensions,
  }
}
