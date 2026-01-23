/**
 * useTreeMap - Composable for Tree Map layout and data management
 * Tree maps display hierarchical classification with top-down structure
 *
 * Uses Dagre for automatic layout:
 * - Topic (root) at top center with pill shape
 * - Categories (depth 1) spread horizontally below topic
 * - Leaves (depth 2+) stacked vertically below their parent category
 * - Connectors: topic bottom -> category top, category bottom -> leaves top
 */
import { computed, ref } from 'vue'

import { Position } from '@vue-flow/core'

import { useLanguage } from '@/composables/useLanguage'
import type { Connection, DiagramNode, MindGraphEdge, MindGraphNode } from '@/types'

import {
  DEFAULT_CATEGORY_SPACING,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  DEFAULT_TOPIC_TO_CATEGORY_GAP,
} from './layoutConfig'
import { calculateDagreLayout, type DagreEdgeInput, type DagreNodeInput } from './useDagreLayout'

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
  categorySpacing?: number // Horizontal spacing between categories (nodeSeparation)
  rankSpacing?: number // Vertical spacing between levels (rankSeparation)
  nodeWidth?: number
  nodeHeight?: number
}

export function useTreeMap(options: TreeMapOptions = {}) {
  const {
    categorySpacing = DEFAULT_CATEGORY_SPACING, // Horizontal spacing between category nodes
    rankSpacing = DEFAULT_TOPIC_TO_CATEGORY_GAP, // Vertical spacing between levels
    nodeWidth = DEFAULT_NODE_WIDTH,
    nodeHeight = DEFAULT_NODE_HEIGHT,
  } = options

  const { t } = useLanguage()
  const data = ref<TreeMapData | null>(null)

  // Generate nodes and edges for tree map using Dagre layout
  function generateLayout(): { nodes: MindGraphNode[]; edges: MindGraphEdge[] } {
    if (!data.value) return { nodes: [], edges: [] }

    const nodes: MindGraphNode[] = []
    const edges: MindGraphEdge[] = []

    const root = data.value.root
    const rootId = root.id || 'tree-topic'
    const categories = root.children || []

    // Build Dagre node and edge lists
    const dagreNodes: DagreNodeInput[] = []
    const dagreEdges: DagreEdgeInput[] = []

    // Add topic node
    dagreNodes.push({ id: rootId, width: nodeWidth, height: nodeHeight })

    // Add category and leaf nodes
    categories.forEach((category, catIndex) => {
      const categoryId = category.id || `tree-cat-${catIndex}`
      dagreNodes.push({ id: categoryId, width: nodeWidth, height: nodeHeight })
      dagreEdges.push({ source: rootId, target: categoryId })

      // Add leaf nodes
      const leaves = category.children || []
      leaves.forEach((leaf, leafIndex) => {
        const leafId = leaf.id || `tree-leaf-${catIndex}-${leafIndex}`
        dagreNodes.push({ id: leafId, width: nodeWidth, height: nodeHeight })

        // Connect leaf to category (first leaf) or previous leaf (chained)
        const sourceId =
          leafIndex === 0
            ? categoryId
            : leaves[leafIndex - 1].id || `tree-leaf-${catIndex}-${leafIndex - 1}`
        dagreEdges.push({ source: sourceId, target: leafId })
      })
    })

    // Calculate layout using Dagre (top-to-bottom direction)
    const layoutResult = calculateDagreLayout(dagreNodes, dagreEdges, {
      direction: 'TB',
      nodeSeparation: categorySpacing,
      rankSeparation: rankSpacing,
      align: 'UL',
      marginX: DEFAULT_PADDING,
      marginY: DEFAULT_PADDING,
    })

    // Calculate center X position of all category nodes to center-align topic node
    let categoryCenterX = 0
    if (categories.length > 0) {
      let minCategoryX = Infinity
      let maxCategoryX = -Infinity
      categories.forEach((category, catIndex) => {
        const categoryId = category.id || `tree-cat-${catIndex}`
        const categoryPos = layoutResult.positions.get(categoryId)
        if (categoryPos) {
          const categoryRight = categoryPos.x + nodeWidth
          if (categoryPos.x < minCategoryX) minCategoryX = categoryPos.x
          if (categoryRight > maxCategoryX) maxCategoryX = categoryRight
        }
      })
      if (minCategoryX !== Infinity && maxCategoryX !== -Infinity) {
        categoryCenterX = (minCategoryX + maxCategoryX) / 2
      }
    }

    // Create topic node with Dagre position, centered above categories
    const topicPos = layoutResult.positions.get(rootId)
    const topicX = categories.length > 0 && categoryCenterX > 0
      ? categoryCenterX - nodeWidth / 2
      : topicPos
        ? topicPos.x
        : 0
    nodes.push({
      id: rootId,
      type: 'topic',
      position: { x: topicX, y: topicPos ? topicPos.y : 0 },
      data: {
        label: root.text,
        nodeType: 'topic',
        diagramType: 'tree_map',
        isDraggable: false,
        isSelectable: true,
      },
      draggable: false,
    })

    // Create category and leaf nodes with Dagre positions
    categories.forEach((category, catIndex) => {
      const categoryId = category.id || `tree-cat-${catIndex}`
      const categoryPos = layoutResult.positions.get(categoryId)

      nodes.push({
        id: categoryId,
        type: 'branch',
        position: categoryPos ? { x: categoryPos.x, y: categoryPos.y } : { x: 0, y: 0 },
        data: {
          label: category.text,
          nodeType: 'branch',
          diagramType: 'tree_map',
          isDraggable: true,
          isSelectable: true,
        },
        draggable: true,
      })

      // Edge from topic to category (bottom to top)
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

      // Add leaf nodes
      const leaves = category.children || []
      leaves.forEach((leaf, leafIndex) => {
        const leafId = leaf.id || `tree-leaf-${catIndex}-${leafIndex}`
        const leafPos = layoutResult.positions.get(leafId)

        nodes.push({
          id: leafId,
          type: 'branch',
          position: leafPos ? { x: leafPos.x, y: leafPos.y } : { x: 0, y: 0 },
          data: {
            label: leaf.text,
            nodeType: 'branch',
            diagramType: 'tree_map',
            isDraggable: true,
            isSelectable: true,
          },
          draggable: true,
        })

        // Edge from category/previous leaf to this leaf
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
      })
    })

    // Add dimension label node below topic if dimension exists
    if (data.value.dimension !== undefined) {
      const topicPosition = layoutResult.positions.get(rootId)
      const dimensionY = topicPosition ? topicPosition.y + nodeHeight + 20 : nodeHeight + 20
      const dimensionX = topicPosition ? topicPosition.x : 0
      nodes.push({
        id: 'dimension-label',
        type: 'label',
        position: { x: dimensionX, y: dimensionY },
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
