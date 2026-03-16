/**
 * Tree Map Loader
 * Tree Map Layout - Custom layout for center-aligned vertical groups:
 * - Topic (root) at top center with pill shape
 * - Categories (depth 1) spread horizontally below topic
 * - Leaves (depth 2+) stacked vertically below their parent category
 * - Each group (category + leaves) forms a straight vertical line, center-aligned
 *
 * Node widths are adaptive to text. Each node is centered within its group column.
 * Group column width = max of all node widths in that group (for layout spacing).
 */
import { getMindmapBranchColor } from '@/config/mindmapColors'
import {
  DEFAULT_CENTER_X,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
  NODE_MIN_DIMENSIONS,
  TREE_MAP_CATEGORY_TO_LEAF_GAP,
  TREE_MAP_LEAF_SPACING,
  TREE_MAP_CATEGORY_SPACING,
  TREE_MAP_TOPIC_TO_CATEGORY_GAP,
} from '@/composables/diagrams/layoutConfig'
import { measureTextDimensions } from '@/stores/specLoader/textMeasurement'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

/** Font size for branch nodes (matches theme default) */
const TREE_MAP_BRANCH_FONT_SIZE = 16
/** Horizontal padding inside node (px-4 = 16px each side) */
const TREE_MAP_NODE_PADDING_X = 32
/** Vertical padding inside node (py-2 = 8px each side) */
const TREE_MAP_NODE_PADDING_Y = 8
/** Max width for leaf text wrap (matches InlineEditableText max-width) */
const TREE_MAP_LEAF_MAX_WIDTH = 150
/** Border width for category nodes (theme branchStrokeWidth) - add to measured width for layout */
const TREE_MAP_CATEGORY_BORDER = 1.5
/** Border width for leaf nodes (theme leafStrokeWidth) - add to measured width for layout */
const TREE_MAP_LEAF_BORDER = 1

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

    // Per-group: measure all node dimensions (width + height for multi-line, like flow map substeps)
    interface GroupDims {
      categoryWidth: number
      categoryHeight: number
      leafWidths: number[]
      leafHeights: number[]
      maxWidth: number
    }
    const groupDimsList: GroupDims[] = []
    categories.forEach((category, catIndex) => {
      const catDims = measureTextDimensions(category.text, TREE_MAP_BRANCH_FONT_SIZE, {
        paddingX: TREE_MAP_NODE_PADDING_X / 2,
        paddingY: TREE_MAP_NODE_PADDING_Y,
        maxWidth: TREE_MAP_LEAF_MAX_WIDTH,
      })
      const catWidth =
        Math.max(catDims.width + 2 * TREE_MAP_CATEGORY_BORDER, NODE_MIN_DIMENSIONS.branch.minWidth)
      const catHeight = Math.max(catDims.height, NODE_MIN_DIMENSIONS.branch.minHeight)
      const leaves = category.children || []
      const leafWidths: number[] = []
      const leafHeights: number[] = []
      let maxW = catWidth
      leaves.forEach((leaf) => {
        const leafDims = measureTextDimensions(leaf.text, TREE_MAP_BRANCH_FONT_SIZE, {
          paddingX: TREE_MAP_NODE_PADDING_X / 2,
          paddingY: TREE_MAP_NODE_PADDING_Y,
          maxWidth: TREE_MAP_LEAF_MAX_WIDTH,
        })
        const leafW =
          Math.max(leafDims.width + 2 * TREE_MAP_LEAF_BORDER, NODE_MIN_DIMENSIONS.branch.minWidth)
        const leafH = Math.max(leafDims.height, NODE_MIN_DIMENSIONS.branch.minHeight)
        leafWidths.push(leafW)
        leafHeights.push(leafH)
        maxW = Math.max(maxW, leafW)
      })
      groupDimsList.push({
        categoryWidth: catWidth,
        categoryHeight: catHeight,
        leafWidths,
        leafHeights,
        maxWidth: maxW,
      })
    })

    const numCategories = categories.length
    const totalCategoriesWidth =
      groupDimsList.reduce((a, g) => a + g.maxWidth, 0) +
      Math.max(0, numCategories - 1) * TREE_MAP_CATEGORY_SPACING
    let columnLeft = DEFAULT_CENTER_X - totalCategoriesWidth / 2

    categories.forEach((category, catIndex) => {
      const categoryId = category.id || `tree-cat-${catIndex}`
      const dims = groupDimsList[catIndex]
      const groupCenterX = columnLeft + dims.maxWidth / 2
      const categoryX = groupCenterX - dims.categoryWidth / 2
      const groupColor = getMindmapBranchColor(catIndex)

      nodes.push({
        id: categoryId,
        text: category.text,
        type: 'branch',
        position: { x: categoryX, y: categoryY },
        style: { width: dims.categoryWidth },
        data: { nodeType: 'branch', groupIndex: catIndex },
      })

      connections.push({
        id: `edge-${rootId}-${categoryId}`,
        source: rootId,
        target: categoryId,
        edgeType: 'step',
        sourcePosition: 'bottom',
        targetPosition: 'top',
        style: { strokeColor: groupColor.border },
      })

      const leaves = category.children || []
      let leafY = categoryY + dims.categoryHeight + TREE_MAP_CATEGORY_TO_LEAF_GAP

      leaves.forEach((leaf, leafIndex) => {
        const leafId = leaf.id || `tree-leaf-${catIndex}-${leafIndex}`
        const leafWidth = dims.leafWidths[leafIndex] ?? NODE_MIN_DIMENSIONS.branch.minWidth
        const leafHeight = dims.leafHeights[leafIndex] ?? NODE_MIN_DIMENSIONS.branch.minHeight
        const leafX = groupCenterX - leafWidth / 2
        nodes.push({
          id: leafId,
          text: leaf.text,
          type: 'branch',
          position: { x: leafX, y: leafY },
          style: { width: leafWidth },
          data: { nodeType: 'leaf', groupIndex: catIndex },
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
          style: { strokeColor: groupColor.border },
        })

        leafY += leafHeight + TREE_MAP_LEAF_SPACING
      })

      columnLeft += dims.maxWidth + TREE_MAP_CATEGORY_SPACING
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
