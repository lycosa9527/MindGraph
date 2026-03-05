/**
 * Tree Map Loader
 * Tree Map Layout - Custom layout for center-aligned vertical groups:
 * - Topic (root) at top center with pill shape
 * - Categories (depth 1) spread horizontally below topic
 * - Leaves (depth 2+) stacked vertically below their parent category
 * - Each group (category + leaves) forms a straight vertical line, center-aligned
 *
 * Root cause of misalignment: variable node widths. Short "省" vs long "广东省" caused
 * left-edge positioning to misalign centers. Fix: measure text per group, use max width
 * for all nodes in group, position by center (nodeX = centerX - maxWidth/2).
 */
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
} from '@/composables/diagrams/layoutConfig'
import { measureTextWidth } from '@/stores/specLoader/textMeasurement'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

/** Font size for branch nodes (matches theme default) */
const TREE_MAP_BRANCH_FONT_SIZE = 16
/** Horizontal padding inside node (px-4 = 16px each side) */
const TREE_MAP_NODE_PADDING_X = 32

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

  const NODE_WIDTH = DEFAULT_NODE_WIDTH
  const NODE_HEIGHT = DEFAULT_NODE_HEIGHT

  // Support both new format (root object) and old format (topic + children)
  let root: TreeNode | undefined = spec.root as TreeNode | undefined
  if (!root && spec.topic !== undefined) {
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

    // Custom layout: center-aligned vertical groups with reduced spacing
    const topicY = DEFAULT_PADDING
    const topicX = DEFAULT_CENTER_X - NODE_WIDTH / 2

    nodes.push({
      id: rootId,
      text: root.text,
      type: 'topic',
      position: { x: topicX, y: topicY },
    })

    const categoryY = topicY + NODE_HEIGHT + TREE_MAP_TOPIC_TO_CATEGORY_GAP

    // Per-group: measure text widths, compute maxWidth for center alignment
    const groupMaxWidths: number[] = []
    categories.forEach((category, catIndex) => {
      const catW =
        measureTextWidth(category.text, TREE_MAP_BRANCH_FONT_SIZE) + TREE_MAP_NODE_PADDING_X
      const leaves = category.children || []
      let maxW = Math.max(catW, NODE_MIN_DIMENSIONS.branch.minWidth)
      leaves.forEach((leaf) => {
        const leafW =
          measureTextWidth(leaf.text, TREE_MAP_BRANCH_FONT_SIZE) + TREE_MAP_NODE_PADDING_X
        maxW = Math.max(maxW, leafW)
      })
      groupMaxWidths.push(maxW)
    })

    const numCategories = categories.length
    const totalCategoriesWidth =
      groupMaxWidths.reduce((a, w) => a + w, 0) +
      Math.max(0, numCategories - 1) * DEFAULT_CATEGORY_SPACING
    let columnLeft = DEFAULT_CENTER_X - totalCategoriesWidth / 2

    categories.forEach((category, catIndex) => {
      const categoryId = category.id || `tree-cat-${catIndex}`
      const maxWidth = groupMaxWidths[catIndex]
      const centerX = columnLeft + maxWidth / 2
      const nodeX = centerX - maxWidth / 2

      nodes.push({
        id: categoryId,
        text: category.text,
        type: 'branch',
        position: { x: nodeX, y: categoryY },
        style: { width: maxWidth },
      })

      connections.push({
        id: `edge-${rootId}-${categoryId}`,
        source: rootId,
        target: categoryId,
        edgeType: 'step',
        sourcePosition: 'bottom',
        targetPosition: 'top',
      })

      const leaves = category.children || []
      let leafY = categoryY + NODE_HEIGHT + TREE_MAP_CATEGORY_TO_LEAF_GAP

      leaves.forEach((leaf, leafIndex) => {
        const leafId = leaf.id || `tree-leaf-${catIndex}-${leafIndex}`
        nodes.push({
          id: leafId,
          text: leaf.text,
          type: 'branch',
          position: { x: nodeX, y: leafY },
          style: { width: maxWidth },
        })

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

        leafY += NODE_HEIGHT + TREE_MAP_LEAF_SPACING
      })

      columnLeft += maxWidth + DEFAULT_CATEGORY_SPACING
    })

    // Add dimension label node if dimension field exists
    if (dimension !== undefined) {
      const topicCenterX = topicX + NODE_WIDTH / 2
      const labelWidth = NODE_MIN_DIMENSIONS.label.minWidth
      nodes.push({
        id: 'dimension-label',
        text: dimension || '',
        type: 'label',
        position: {
          x: topicCenterX - labelWidth / 2,
          y: topicY + NODE_HEIGHT + 20,
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
