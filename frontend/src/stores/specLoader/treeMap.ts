/**
 * Tree Map Loader
 * Tree Map Layout - Matches old JS tree-renderer.js:
 * - Topic (root) at top center with pill shape
 * - Categories (depth 1) spread horizontally below topic
 * - Leaves (depth 2+) stacked vertically below their parent category
 */
import {
  DEFAULT_CATEGORY_SPACING,
  DEFAULT_CENTER_X,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  DEFAULT_TOPIC_TO_CATEGORY_GAP,
  NODE_MIN_DIMENSIONS,
} from '@/composables/diagrams/layoutConfig'
import { calculateDagreLayout } from '@/composables/diagrams/useDagreLayout'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

interface TreeNode {
  id?: string
  text: string
  children?: TreeNode[]
}

/**
 * Load tree map spec into diagram nodes and connections
 *
 * @param spec - Tree map spec with root or topic + children
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadTreeMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Layout constants from layoutConfig
  const NODE_WIDTH = DEFAULT_NODE_WIDTH
  const NODE_HEIGHT = DEFAULT_NODE_HEIGHT

  // Support both new format (root object) and old format (topic + children)
  let root: TreeNode | undefined = spec.root as TreeNode | undefined
  if (!root && spec.topic !== undefined) {
    // Convert old format to new format
    root = {
      id: 'tree-topic',
      text: (spec.topic as string) || '',
      children: (spec.children as TreeNode[]) || [],
    }
  }

  const dimension = spec.dimension as string | undefined
  const alternativeDimensions = spec.alternative_dimensions as string[] | undefined

  if (root) {
    const rootId = root.id || 'tree-topic'
    const categories = root.children || []

    // Build node list for Dagre layout
    interface DagreNode {
      id: string
      width: number
      height: number
    }
    interface DagreEdge {
      source: string
      target: string
    }

    const dagreNodes: DagreNode[] = []
    const dagreEdges: DagreEdge[] = []

    // Add topic node
    dagreNodes.push({ id: rootId, width: NODE_WIDTH, height: NODE_HEIGHT })

    // Add category and leaf nodes
    categories.forEach((category, catIndex) => {
      const categoryId = category.id || `tree-cat-${catIndex}`
      dagreNodes.push({ id: categoryId, width: NODE_WIDTH, height: NODE_HEIGHT })
      dagreEdges.push({ source: rootId, target: categoryId })

      // Add leaf nodes
      const leaves = category.children || []
      leaves.forEach((leaf, leafIndex) => {
        const leafId = leaf.id || `tree-leaf-${catIndex}-${leafIndex}`
        dagreNodes.push({ id: leafId, width: NODE_WIDTH, height: NODE_HEIGHT })

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
      nodeSeparation: DEFAULT_CATEGORY_SPACING,
      rankSeparation: DEFAULT_TOPIC_TO_CATEGORY_GAP,
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
          const categoryRight = categoryPos.x + NODE_WIDTH
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
    const topicX =
      categories.length > 0 && categoryCenterX > 0
        ? categoryCenterX - NODE_WIDTH / 2
        : topicPos
          ? topicPos.x
          : DEFAULT_CENTER_X - NODE_WIDTH / 2
    nodes.push({
      id: rootId,
      text: root.text,
      type: 'topic',
      position: { x: topicX, y: topicPos ? topicPos.y : 60 },
    })

    // Create category and leaf nodes with Dagre positions
    categories.forEach((category, catIndex) => {
      const categoryId = category.id || `tree-cat-${catIndex}`
      const categoryPos = layoutResult.positions.get(categoryId)

      nodes.push({
        id: categoryId,
        text: category.text,
        type: 'branch',
        position: categoryPos ? { x: categoryPos.x, y: categoryPos.y } : { x: 0, y: 0 },
      })

      // Connection from topic to category (T-shape step edge)
      connections.push({
        id: `edge-${rootId}-${categoryId}`,
        source: rootId,
        target: categoryId,
        edgeType: 'step',
        sourcePosition: 'bottom',
        targetPosition: 'top',
      })

      // Add leaf nodes
      const leaves = category.children || []
      leaves.forEach((leaf, leafIndex) => {
        const leafId = leaf.id || `tree-leaf-${catIndex}-${leafIndex}`
        const leafPos = layoutResult.positions.get(leafId)

        nodes.push({
          id: leafId,
          text: leaf.text,
          type: 'branch',
          position: leafPos ? { x: leafPos.x, y: leafPos.y } : { x: 0, y: 0 },
        })

        // Connection from category/previous leaf to this leaf (straight vertical)
        const sourceId =
          leafIndex === 0
            ? categoryId
            : leaves[leafIndex - 1].id || `tree-leaf-${catIndex}-${leafIndex - 1}`
        connections.push({
          id: `edge-${sourceId}-${leafId}`,
          source: sourceId,
          target: leafId,
          edgeType: 'tree',
          sourcePosition: 'bottom',
          targetPosition: 'top',
        })
      })
    })

    // Add dimension label node if dimension field exists
    // Position it right below the topic node, center-aligned under the topic
    if (dimension !== undefined) {
      const topicPos = nodes.find((n) => n.id === rootId)?.position
      const topicCenterX = (topicPos?.x ?? DEFAULT_CENTER_X - NODE_WIDTH / 2) + NODE_WIDTH / 2
      const labelWidth = NODE_MIN_DIMENSIONS.label.minWidth
      nodes.push({
        id: 'dimension-label',
        text: dimension || '',
        type: 'label',
        position: {
          x: topicCenterX - labelWidth / 2,
          y: (topicPos?.y ?? 60) + NODE_HEIGHT + 20,
        },
      })
    }
  }

  return {
    nodes,
    connections,
    metadata: {
      dimension,
      alternativeDimensions,
    },
  }
}
