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
  TREE_MAP_TOPIC_TO_CATEGORY_GAP,
} from '@/composables/diagrams/layoutConfig'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import { measureTextDimensions } from '@/stores/specLoader/textMeasurement'
import { computeScriptAwareMaxWidth } from '@/stores/specLoader/textMeasurementFallback'
import type { Connection, DiagramNode } from '@/types'

import { measureTreeMapTopicDimensions, treeMapTopicPositionFromLayout } from './treeMapTopicLayout'
import type { SpecLoaderResult } from './types'

/** Font size for branch nodes (matches theme default) */
const TREE_MAP_BRANCH_FONT_SIZE = 16
/** Horizontal padding inside node (px-4 = 16px each side) */
const TREE_MAP_NODE_PADDING_X = 32
/** Vertical padding inside node (py-2 = 8px each side) */
const TREE_MAP_NODE_PADDING_Y = 8
/** Base max width for leaf text wrap (adapts per-script via computeScriptAwareMaxWidth) */
const TREE_MAP_LEAF_BASE_MAX_WIDTH = 150
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
    const rootId = 'tree-topic'
    const categories = root.children || []

    // Custom layout: center-aligned vertical groups with reduced spacing
    const topicY = DEFAULT_PADDING
    const topicDims = measureTreeMapTopicDimensions(root.text)
    const topicPos = treeMapTopicPositionFromLayout(topicDims.width, topicY)

    nodes.push({
      id: rootId,
      text: root.text,
      type: 'topic',
      position: topicPos,
      style: { width: topicDims.width, height: topicDims.height },
    })

    const categoryY = topicY + topicDims.height + TREE_MAP_TOPIC_TO_CATEGORY_GAP

    // Per-group: measure all node dimensions (width + height for multi-line, like flow map substeps)
    interface GroupDims {
      categoryWidth: number
      categoryHeight: number
      leafWidths: number[]
      leafHeights: number[]
      maxWidth: number
    }
    const groupDimsList: GroupDims[] = []
    categories.forEach((category, _catIndex) => {
      const catMaxW = computeScriptAwareMaxWidth(category.text, TREE_MAP_LEAF_BASE_MAX_WIDTH)
      const catDims = measureTextDimensions(category.text, TREE_MAP_BRANCH_FONT_SIZE, {
        paddingX: TREE_MAP_NODE_PADDING_X / 2,
        paddingY: TREE_MAP_NODE_PADDING_Y,
        maxWidth: catMaxW,
      })
      const catWidth = Math.max(
        catDims.width + 2 * TREE_MAP_CATEGORY_BORDER,
        NODE_MIN_DIMENSIONS.branch.minWidth
      )
      const catHeight = Math.max(catDims.height, NODE_MIN_DIMENSIONS.branch.minHeight)
      const leaves = category.children || []
      const leafWidths: number[] = []
      const leafHeights: number[] = []
      let maxW = catWidth
      leaves.forEach((leaf) => {
        const leafMaxW = computeScriptAwareMaxWidth(leaf.text, TREE_MAP_LEAF_BASE_MAX_WIDTH)
        const leafDims = measureTextDimensions(leaf.text, TREE_MAP_BRANCH_FONT_SIZE, {
          paddingX: TREE_MAP_NODE_PADDING_X / 2,
          paddingY: TREE_MAP_NODE_PADDING_Y,
          maxWidth: leafMaxW,
        })
        const leafW = Math.max(
          leafDims.width + 2 * TREE_MAP_LEAF_BORDER,
          NODE_MIN_DIMENSIONS.branch.minWidth
        )
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
      const categoryId = `tree-cat-${catIndex}`
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
        const leafId = `tree-leaf-${catIndex}-${leafIndex}`
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

        const sourceId = leafIndex === 0 ? categoryId : `tree-leaf-${catIndex}-${leafIndex - 1}`
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
      const topicCenterX = DEFAULT_CENTER_X
      const labelWidth = NODE_MIN_DIMENSIONS.label.minWidth
      nodes.push({
        id: 'dimension-label',
        text: dimension || '',
        type: 'label',
        position: {
          x: topicCenterX - labelWidth / 2,
          y: topicY + topicDims.height + 20,
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

function resolveTreeMapBox(
  nodeId: string,
  nodeDimensions: Record<string, { width: number; height: number }>,
  measure: () => { width: number; height: number }
): { width: number; height: number } {
  const measured = measure()
  const pinia = nodeDimensions[nodeId]
  if (!pinia || pinia.height <= 0) {
    return measured
  }
  return { width: measured.width, height: pinia.height }
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
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return nodes
  }

  const topicIdx = nodes.findIndex((n) => n.id === 'tree-topic' && n.type === 'topic')
  if (topicIdx === -1) {
    return nodes
  }

  const topicNode = nodes[topicIdx]
  const topicText = topicNode.text ?? ''

  const topicDims = resolveTreeMapBox('tree-topic', nodeDimensions, () =>
    measureTreeMapTopicDimensions(topicText)
  )

  const topicY = topicNode.position?.y ?? DEFAULT_PADDING
  const topicPos = treeMapTopicPositionFromLayout(topicDims.width, topicY)

  const catIds = nodes
    .map((n) => n.id)
    .filter((id): id is string => !!id && /^tree-cat-\d+$/.test(id))
    .sort((a, b) => {
      const ia = parseInt(a.replace('tree-cat-', ''), 10)
      const ib = parseInt(b.replace('tree-cat-', ''), 10)
      return ia - ib
    })

  const groupDimsList: TreeMapGroupDims[] = []

  catIds.forEach((catId) => {
    const catIndex = parseInt(catId.replace('tree-cat-', ''), 10)
    const catNode = nodes.find((n) => n.id === catId)
    const catText = catNode?.text ?? ''

    const catAdaptiveMaxW = computeScriptAwareMaxWidth(catText, TREE_MAP_LEAF_BASE_MAX_WIDTH)
    const catBox = resolveTreeMapBox(catId, nodeDimensions, () => {
      const catDims = measureTextDimensions(catText, TREE_MAP_BRANCH_FONT_SIZE, {
        paddingX: TREE_MAP_NODE_PADDING_X / 2,
        paddingY: TREE_MAP_NODE_PADDING_Y,
        maxWidth: catAdaptiveMaxW,
      })
      const catWidth = Math.max(
        catDims.width + 2 * TREE_MAP_CATEGORY_BORDER,
        NODE_MIN_DIMENSIONS.branch.minWidth
      )
      const catHeight = Math.max(catDims.height, NODE_MIN_DIMENSIONS.branch.minHeight)
      return { width: catWidth, height: catHeight }
    })

    const leafNodes = nodes
      .filter((n) => {
        const id = n.id ?? ''
        const m = id.match(new RegExp(`^tree-leaf-${catIndex}-(\\d+)$`))
        return Boolean(m)
      })
      .sort((a, b) => {
        const ma = a.id?.match(/^tree-leaf-\d+-(\d+)$/)
        const mb = b.id?.match(/^tree-leaf-\d+-(\d+)$/)
        return parseInt(ma?.[1] ?? '0', 10) - parseInt(mb?.[1] ?? '0', 10)
      })

    const leafWidths: number[] = []
    const leafHeights: number[] = []
    let maxW = catBox.width

    leafNodes.forEach((leaf) => {
      const leafId = leaf.id ?? ''
      const leafText = leaf.text ?? ''
      const leafAdaptiveMaxW = computeScriptAwareMaxWidth(leafText, TREE_MAP_LEAF_BASE_MAX_WIDTH)
      const leafBox = resolveTreeMapBox(leafId, nodeDimensions, () => {
        const leafDims = measureTextDimensions(leafText, TREE_MAP_BRANCH_FONT_SIZE, {
          paddingX: TREE_MAP_NODE_PADDING_X / 2,
          paddingY: TREE_MAP_NODE_PADDING_Y,
          maxWidth: leafAdaptiveMaxW,
        })
        const leafW = Math.max(
          leafDims.width + 2 * TREE_MAP_LEAF_BORDER,
          NODE_MIN_DIMENSIONS.branch.minWidth
        )
        const leafH = Math.max(leafDims.height, NODE_MIN_DIMENSIONS.branch.minHeight)
        return { width: leafW, height: leafH }
      })
      leafWidths.push(leafBox.width)
      leafHeights.push(leafBox.height)
      maxW = Math.max(maxW, leafBox.width)
    })

    groupDimsList.push({
      categoryWidth: catBox.width,
      categoryHeight: catBox.height,
      leafWidths,
      leafHeights,
      maxWidth: maxW,
    })
  })

  const byId = new Map<string, DiagramNode>()
  for (const n of nodes) {
    if (n.id) {
      byId.set(n.id, { ...n })
    }
  }

  const topicMerged = byId.get('tree-topic')
  if (topicMerged) {
    byId.set('tree-topic', {
      ...topicMerged,
      position: topicPos,
      style: {
        ...topicMerged.style,
        width: topicDims.width,
        height: topicDims.height,
      },
    })
  }

  const categoryY = topicY + topicDims.height + TREE_MAP_TOPIC_TO_CATEGORY_GAP
  const numCategories = catIds.length
  const totalCategoriesWidth =
    groupDimsList.reduce((a, g) => a + g.maxWidth, 0) +
    Math.max(0, numCategories - 1) * TREE_MAP_CATEGORY_SPACING
  let columnLeft = DEFAULT_CENTER_X - totalCategoriesWidth / 2

  catIds.forEach((catId, catIndex) => {
    const dims = groupDimsList[catIndex]
    const groupCenterX = columnLeft + dims.maxWidth / 2
    const categoryX = groupCenterX - dims.categoryWidth / 2
    const catNode = byId.get(catId)
    if (catNode) {
      byId.set(catId, {
        ...catNode,
        position: { x: categoryX, y: categoryY },
        style: { ...catNode.style, width: dims.categoryWidth },
      })
    }

    const leafNodes = nodes
      .filter((n) => {
        const id = n.id ?? ''
        const m = id.match(
          new RegExp(`^tree-leaf-${parseInt(catId.replace('tree-cat-', ''), 10)}-(\\d+)$`)
        )
        return Boolean(m)
      })
      .sort((a, b) => {
        const ma = a.id?.match(/^tree-leaf-\d+-(\d+)$/)
        const mb = b.id?.match(/^tree-leaf-\d+-(\d+)$/)
        return parseInt(ma?.[1] ?? '0', 10) - parseInt(mb?.[1] ?? '0', 10)
      })

    let leafY = categoryY + dims.categoryHeight + TREE_MAP_CATEGORY_TO_LEAF_GAP

    leafNodes.forEach((leaf, leafIndex) => {
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
          style: { ...leafNode.style, width: leafWidth },
        })
      }
      leafY += leafHeight + TREE_MAP_LEAF_SPACING
    })

    columnLeft += dims.maxWidth + TREE_MAP_CATEGORY_SPACING
  })

  const dimLabel = byId.get('dimension-label')
  if (dimLabel) {
    const piniaDim = nodeDimensions['dimension-label']
    const labelWidth =
      piniaDim && piniaDim.width > 0
        ? piniaDim.width
        : NODE_MIN_DIMENSIONS.label.minWidth
    byId.set('dimension-label', {
      ...dimLabel,
      position: {
        x: DEFAULT_CENTER_X - labelWidth / 2,
        y: topicY + topicDims.height + 20,
      },
    })
  }

  return nodes.map((n) => {
    if (!n.id) return n
    return byId.get(n.id) ?? n
  })
}
