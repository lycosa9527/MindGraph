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
import {
  DEFAULT_CENTER_X,
  DEFAULT_PADDING,
  NODE_MIN_DIMENSIONS,
  TREE_MAP_CATEGORY_SPACING,
  TREE_MAP_CATEGORY_TO_LEAF_GAP,
  TREE_MAP_LEAF_SPACING,
} from '@/composables/diagrams/layoutConfig'
import type { Connection, DiagramNode } from '@/types'
import { thinkingMapStampedBranchColor } from '@/utils/thinkingMapChrome'
import {
  TREE_MAP_UID_DATA_KEY,
  TREE_TOPIC_NODE_ID,
  stampTreeCategoryData,
  stampTreeLeafData,
  takeTreeMapStableId,
  treeMapColumnsOf,
} from '@/utils/treeMapIdentity'
import {
  measureTreeMapDimensionLabelBox,
  resolveTreeMapDimensionLabelBox,
  treeMapCategoryTopY,
  treeMapDimensionLabelPosition,
} from '@/utils/treeMapLabelLayout'
import {
  TREE_MAP_BRANCH_FONT_SIZE,
  TREE_MAP_LEAF_FONT_SIZE,
  measureTreeMapNodeBox,
} from '@/utils/treeMapNodeBox'

import {
  collectTreeMapNodeMeasureSpecs,
  collectTreeMapSpecMeasureSpecs,
  treeMapBranchMeasureOptions,
  withTreeMapTextMeasureCache,
} from './treeMapMeasureBatch'
import { measureTreeMapTopicDimensions, treeMapTopicPositionFromLayout } from './treeMapTopicLayout'
import type { SpecLoaderResult } from './types'

interface TreeNode {
  id?: string
  text: string
  textSecondary?: string
  children?: TreeNode[]
}

function glossFields(raw: unknown): { textSecondary?: string } {
  const line = typeof raw === 'string' ? raw.trim() : ''
  return line ? { textSecondary: line } : {}
}

/**
 * Load tree map spec into diagram nodes and connections
 *
 * @param spec - Tree map spec with root or topic + children
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadTreeMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  return withTreeMapTextMeasureCache(collectTreeMapSpecMeasureSpecs(spec), () =>
    loadTreeMapSpecMeasured(spec)
  )
}

function loadTreeMapSpecMeasured(spec: Record<string, unknown>): SpecLoaderResult {
  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Support both new format (root object) and old format (topic + children)
  let root: TreeNode | undefined = spec.root as TreeNode | undefined
  if (!root && spec.topic !== undefined) {
    root = {
      id: TREE_TOPIC_NODE_ID,
      text: (spec.topic as string) || '',
      children: (spec.children as TreeNode[]) || [],
    }
  }

  const dimension = spec.dimension as string | undefined
  const alternativeDimensions = spec.alternative_dimensions as string[] | undefined

  if (root) {
    const rootId = TREE_TOPIC_NODE_ID
    const categories = root.children || []
    const claimedIds = new Set<string>([TREE_TOPIC_NODE_ID, 'dimension-label'])

    // Custom layout: center-aligned vertical groups with reduced spacing
    const topicY = DEFAULT_PADDING
    const topicDims = measureTreeMapTopicDimensions(root.text)
    const topicPos = treeMapTopicPositionFromLayout(topicDims.width, topicY)

    nodes.push({
      id: rootId,
      text: root.text,
      ...glossFields(root.textSecondary),
      type: 'topic',
      position: topicPos,
      style: { width: topicDims.width, height: topicDims.height },
    })

    const labelBox =
      dimension !== undefined
        ? measureTreeMapDimensionLabelBox(
            dimension || '',
            typeof spec.dimensionSecondary === 'string' ? spec.dimensionSecondary : undefined
          )
        : null
    const categoryY = treeMapCategoryTopY(topicY, topicDims.height, labelBox)

    // Per-group: measure all node dimensions (width + height for wrapped lines)
    interface GroupDims {
      categoryWidth: number
      categoryHeight: number
      leafWidths: number[]
      leafHeights: number[]
      maxWidth: number
    }
    const groupDimsList: GroupDims[] = []
    categories.forEach((category, _catIndex) => {
      const catBox = measureTreeMapNodeBox(category.text, {
        role: 'category',
        fontSize: TREE_MAP_BRANCH_FONT_SIZE,
        secondary: category.textSecondary,
      })
      const catWidth = catBox.width
      const catHeight = catBox.height
      const leaves = category.children || []
      const leafWidths: number[] = []
      const leafHeights: number[] = []
      let maxW = catWidth
      leaves.forEach((leaf) => {
        const leafBox = measureTreeMapNodeBox(leaf.text, {
          role: 'leaf',
          fontSize: TREE_MAP_LEAF_FONT_SIZE,
          secondary: leaf.textSecondary,
        })
        const leafW = leafBox.width
        const leafH = leafBox.height
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
      const categoryId = takeTreeMapStableId(claimedIds, category.id)
      const dims = groupDimsList[catIndex]
      const groupCenterX = columnLeft + dims.maxWidth / 2
      const categoryX = groupCenterX - dims.categoryWidth / 2
      const groupColor = thinkingMapStampedBranchColor(catIndex)

      nodes.push({
        id: categoryId,
        text: category.text,
        ...glossFields(category.textSecondary),
        type: 'branch',
        position: { x: categoryX, y: categoryY },
        style: { width: dims.categoryWidth },
        data: stampTreeCategoryData(catIndex, { [TREE_MAP_UID_DATA_KEY]: categoryId }),
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
        const leafId = takeTreeMapStableId(claimedIds, leaf.id)
        const leafWidth = dims.leafWidths[leafIndex] ?? NODE_MIN_DIMENSIONS.branch.minWidth
        const leafHeight = dims.leafHeights[leafIndex] ?? NODE_MIN_DIMENSIONS.branch.minHeight
        const leafX = groupCenterX - leafWidth / 2
        nodes.push({
          id: leafId,
          text: leaf.text,
          ...glossFields(leaf.textSecondary),
          type: 'branch',
          position: { x: leafX, y: leafY },
          style: { width: leafWidth },
          data: stampTreeLeafData(catIndex, leafIndex, categoryId, {
            [TREE_MAP_UID_DATA_KEY]: leafId,
          }),
        })

        const sourceId = leafIndex === 0 ? categoryId : nodes[nodes.length - 2].id
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
    if (dimension !== undefined && labelBox) {
      nodes.push({
        id: 'dimension-label',
        text: dimension || '',
        ...glossFields(spec.dimensionSecondary),
        type: 'label',
        position: treeMapDimensionLabelPosition(topicY, topicDims.height, labelBox),
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

function resolveTreeMapBox(
  nodeId: string,
  nodeDimensions: Record<string, { width: number; height: number }>,
  measure: () => { width: number; height: number }
): { width: number; height: number } {
  const measured = measure()
  const pinia = nodeDimensions[nodeId]
  if (!pinia || pinia.height <= 0 || pinia.width <= 0) {
    return measured
  }
  return {
    width: Math.max(measured.width, pinia.width),
    height: Math.max(measured.height, pinia.height),
  }
}

interface TreeMapGroupDims {
  categoryWidth: number
  categoryHeight: number
  leafWidths: number[]
  leafHeights: number[]
  maxWidth: number
}

/**
 * Recompute tree map node positions and sizes from current nodes + Pinia DOM measurements.
 * Prefers `nodeDimensions` (after KaTeX/markdown) over text measurement when available.
 */
export function recalculateTreeMapLayout(
  nodes: DiagramNode[],
  nodeDimensions: Record<string, { width: number; height: number }> = {}
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) return nodes
  return withTreeMapTextMeasureCache(collectTreeMapNodeMeasureSpecs(nodes), () =>
    recalculateTreeMapLayoutMeasured(nodes, nodeDimensions)
  )
}

function recalculateTreeMapLayoutMeasured(
  nodes: DiagramNode[],
  nodeDimensions: Record<string, { width: number; height: number }>
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return nodes
  }

  const topicIdx = nodes.findIndex((n) => n.id === TREE_TOPIC_NODE_ID && n.type === 'topic')
  if (topicIdx === -1) {
    return nodes
  }

  const topicNode = nodes[topicIdx]
  const topicText = topicNode.text ?? ''

  const topicDims = resolveTreeMapBox(TREE_TOPIC_NODE_ID, nodeDimensions, () =>
    measureTreeMapTopicDimensions(topicText, topicNode.style, topicNode.textSecondary)
  )

  const topicY = topicNode.position?.y ?? DEFAULT_PADDING
  const topicPos = treeMapTopicPositionFromLayout(topicDims.width, topicY)

  const columns = treeMapColumnsOf(nodes)
  const groupDimsList: TreeMapGroupDims[] = []

  for (const column of columns) {
    const catNode = column.category
    const catId = catNode.id ?? ''
    const catBox = resolveTreeMapBox(catId, nodeDimensions, () =>
      measureTreeMapNodeBox(catNode.text ?? '', treeMapBranchMeasureOptions(catNode, 'category'))
    )

    const leafWidths: number[] = []
    const leafHeights: number[] = []
    let maxW = catBox.width

    for (const leaf of column.leaves) {
      const leafBox = resolveTreeMapBox(leaf.id ?? '', nodeDimensions, () =>
        measureTreeMapNodeBox(leaf.text ?? '', treeMapBranchMeasureOptions(leaf, 'leaf'))
      )
      leafWidths.push(leafBox.width)
      leafHeights.push(leafBox.height)
      maxW = Math.max(maxW, leafBox.width)
    }

    groupDimsList.push({
      categoryWidth: catBox.width,
      categoryHeight: catBox.height,
      leafWidths,
      leafHeights,
      maxWidth: maxW,
    })
  }

  const byId = new Map<string, DiagramNode>()
  for (const n of nodes) {
    if (n.id) {
      byId.set(n.id, { ...n })
    }
  }

  const topicMerged = byId.get(TREE_TOPIC_NODE_ID)
  if (topicMerged) {
    byId.set(TREE_TOPIC_NODE_ID, {
      ...topicMerged,
      position: topicPos,
      style: {
        ...topicMerged.style,
        width: topicDims.width,
        height: topicDims.height,
      },
    })
  }

  const dimLabel = byId.get('dimension-label')
  const labelBox = dimLabel
    ? resolveTreeMapDimensionLabelBox(
        dimLabel.text ?? '',
        dimLabel.textSecondary,
        nodeDimensions['dimension-label']
      )
    : null
  const categoryY = treeMapCategoryTopY(topicY, topicDims.height, labelBox)
  const numCategories = columns.length
  const totalCategoriesWidth =
    groupDimsList.reduce((a, g) => a + g.maxWidth, 0) +
    Math.max(0, numCategories - 1) * TREE_MAP_CATEGORY_SPACING
  let columnLeft = DEFAULT_CENTER_X - totalCategoriesWidth / 2

  columns.forEach((column, catIndex) => {
    const dims = groupDimsList[catIndex]
    if (!dims) return
    const groupCenterX = columnLeft + dims.maxWidth / 2
    const categoryX = groupCenterX - dims.categoryWidth / 2
    const catId = column.category.id
    const catNode = catId ? byId.get(catId) : undefined
    if (catId && catNode) {
      byId.set(catId, {
        ...catNode,
        position: { x: categoryX, y: categoryY },
        style: {
          ...catNode.style,
          width: dims.categoryWidth,
          height: dims.categoryHeight,
        },
      })
    }

    let leafY = categoryY + dims.categoryHeight + TREE_MAP_CATEGORY_TO_LEAF_GAP

    column.leaves.forEach((leaf, leafIndex) => {
      const leafId = leaf.id
      if (!leafId) return
      const leafWidth = dims.leafWidths[leafIndex] ?? NODE_MIN_DIMENSIONS.branch.minWidth
      const leafHeight = dims.leafHeights[leafIndex] ?? NODE_MIN_DIMENSIONS.branch.minHeight
      const leafX = groupCenterX - leafWidth / 2
      const leafNode = byId.get(leafId)
      if (leafNode) {
        byId.set(leafId, {
          ...leafNode,
          position: { x: leafX, y: leafY },
          style: { ...leafNode.style, width: leafWidth, height: leafHeight },
        })
      }
      leafY += leafHeight + TREE_MAP_LEAF_SPACING
    })

    columnLeft += dims.maxWidth + TREE_MAP_CATEGORY_SPACING
  })

  if (dimLabel && labelBox) {
    byId.set('dimension-label', {
      ...dimLabel,
      position: treeMapDimensionLabelPosition(topicY, topicDims.height, labelBox),
    })
  }

  return nodes.map((n) => {
    if (!n.id) return n
    return byId.get(n.id) ?? n
  })
}
