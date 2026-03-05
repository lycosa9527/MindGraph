/**
 * useTreeMap - Composable for Tree Map layout and data management
 * Tree maps display hierarchical classification with top-down structure
 *
 * Custom layout for center-aligned vertical groups:
 * - Topic (root) at top center with pill shape
 * - Categories (depth 1) spread horizontally below topic
 * - Leaves (depth 2+) stacked vertically below their parent category
 * - Each group (category + leaves) forms a straight vertical line, center-aligned
 */
import { computed, ref } from 'vue'

import { Position } from '@vue-flow/core'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import {
  DEFAULT_CATEGORY_SPACING,
  DEFAULT_CENTER_X,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  NODE_MIN_DIMENSIONS,
  TREE_MAP_CATEGORY_TO_LEAF_GAP,
  TREE_MAP_LEAF_SPACING,
  TREE_MAP_TOPIC_TO_CATEGORY_GAP,
} from './layoutConfig'
import { measureTextWidth } from '@/stores/specLoader/textMeasurement'

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
  categorySpacing?: number
  nodeWidth?: number
  nodeHeight?: number
}

export function useTreeMap(options: TreeMapOptions = {}) {
  const {
    categorySpacing = DEFAULT_CATEGORY_SPACING,
    nodeWidth = DEFAULT_NODE_WIDTH,
    nodeHeight = DEFAULT_NODE_HEIGHT,
  } = options

  const { t } = useLanguage()
  const data = ref<TreeMapData | null>(null)

  // Generate nodes and edges using custom center-aligned layout
  function generateLayout(): { nodes: MindGraphNode[]; edges: MindGraphEdge[] } {
    if (!data.value) return { nodes: [], edges: [] }

    const nodes: MindGraphNode[] = []
    const edges: MindGraphEdge[] = []

    const root = data.value.root
    const rootId = root.id || 'tree-topic'
    const categories = root.children || []

    const topicY = DEFAULT_PADDING
    const topicX = DEFAULT_CENTER_X - nodeWidth / 2

    nodes.push({
      id: rootId,
      type: 'topic',
      position: { x: topicX, y: topicY },
      data: {
        label: root.text,
        nodeType: 'topic',
        diagramType: 'tree_map',
        isDraggable: false,
        isSelectable: true,
      },
      draggable: false,
    })

    const categoryY = topicY + nodeHeight + TREE_MAP_TOPIC_TO_CATEGORY_GAP
    const BRANCH_FONT_SIZE = 16
    const NODE_PADDING_X = 32

    const groupMaxWidths: number[] = []
    categories.forEach((category, catIndex) => {
      const catW = measureTextWidth(category.text, BRANCH_FONT_SIZE) + NODE_PADDING_X
      const leaves = category.children || []
      let maxW = Math.max(catW, NODE_MIN_DIMENSIONS.branch.minWidth)
      leaves.forEach((leaf) => {
        const leafW = measureTextWidth(leaf.text, BRANCH_FONT_SIZE) + NODE_PADDING_X
        maxW = Math.max(maxW, leafW)
      })
      groupMaxWidths.push(maxW)
    })

    const numCategories = categories.length
    const totalCategoriesWidth =
      groupMaxWidths.reduce((a, w) => a + w, 0) +
      Math.max(0, numCategories - 1) * categorySpacing
    let columnLeft = DEFAULT_CENTER_X - totalCategoriesWidth / 2

    categories.forEach((category, catIndex) => {
      const categoryId = category.id || `tree-cat-${catIndex}`
      const maxWidth = groupMaxWidths[catIndex]
      const nodeX = columnLeft

      nodes.push({
        id: categoryId,
        type: 'branch',
        position: { x: nodeX, y: categoryY },
        width: maxWidth,
        data: {
          label: category.text,
          nodeType: 'branch',
          diagramType: 'tree_map',
          isDraggable: true,
          isSelectable: true,
          style: { width: maxWidth },
        },
        draggable: true,
      })

      edges.push({
        id: `edge-${rootId}-${categoryId}`,
        source: rootId,
        target: categoryId,
        type: 'step',
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        data: {
          edgeType: 'step' as const,
          style: { strokeColor: '#bbb' },
        },
      })

      const leaves = category.children || []
      let leafY = categoryY + nodeHeight + TREE_MAP_CATEGORY_TO_LEAF_GAP

      leaves.forEach((leaf, leafIndex) => {
        const leafId = leaf.id || `tree-leaf-${catIndex}-${leafIndex}`
        nodes.push({
          id: leafId,
          type: 'branch',
          position: { x: nodeX, y: leafY },
          width: maxWidth,
          data: {
            label: leaf.text,
            nodeType: 'branch',
            diagramType: 'tree_map',
            isDraggable: true,
            isSelectable: true,
            style: { width: maxWidth },
          },
          draggable: true,
        })

        const sourceId =
          leafIndex === 0
            ? categoryId
            : leaves[leafIndex - 1].id || `tree-leaf-${catIndex}-${leafIndex - 1}`
        edges.push({
          id: `edge-${sourceId}-${leafId}`,
          source: sourceId,
          target: leafId,
          type: 'tree',
          sourcePosition: Position.Bottom,
          targetPosition: Position.Top,
          data: {
            edgeType: 'step' as const,
            style: { strokeColor: '#ccc' },
          },
        })

        leafY += nodeHeight + TREE_MAP_LEAF_SPACING
      })

      columnLeft += maxWidth + categorySpacing
    })

    if (data.value.dimension !== undefined) {
      const topicCenterX = topicX + nodeWidth / 2
      const labelWidth = 100
      nodes.push({
        id: 'dimension-label',
        type: 'label',
        position: {
          x: topicCenterX - labelWidth / 2,
          y: topicY + nodeHeight + 20,
        },
        data: {
          label:
            data.value.dimension ||
            t('diagram.dimensionPlaceholder', 'Classification by: click to specify...'),
          nodeType: 'label',
          diagramType: 'tree_map',
          isDraggable: false,
          isSelectable: true,
          isPlaceholder: !data.value.dimension,
        },
        draggable: false,
        selectable: true,
      })
    }

    return { nodes, edges }
  }

  // Convert tree data to Vue Flow nodes
  const nodes = computed<MindGraphNode[]>(() => {
    return generateLayout().nodes
  })

  // Generate edges
  const edges = computed<MindGraphEdge[]>(() => {
    return generateLayout().edges
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

  // Add child to a node
  function addChild(parentId: string, text?: string, selectedNodeId?: string): boolean {
    if (!data.value) return false

    // Selection validation - must select a node that's not the root
    if (selectedNodeId && selectedNodeId === data.value.root.id) {
      console.warn('Cannot add children to root node directly')
      return false
    }

    // If selectedNodeId is provided, use it as parentId
    const targetParentId = selectedNodeId || parentId

    // Use default translated text if not provided
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
