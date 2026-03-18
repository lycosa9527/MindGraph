<script setup lang="ts">
/**
 * BraceOverlay - Draws proper curly braces for brace maps
 * Creates unified brace shapes connecting parents to their children groups
 * Also draws alternative dimensions at bottom (like archive brace-renderer.js)
 *
 * Brace structure (continuous path):
 *   ╮        1. Top curve
 *   |        2. Vertical line
 *    \       3. Diagonal to V-tip
 *     <      4. V-tip point (sharp, miter join)
 *    /       5. Diagonal from V-tip
 *   |        6. Vertical line
 *   ╯        7. Bottom curve
 */
import { computed } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { getMindmapBranchColor } from '@/config/mindmapColors'
import { DEFAULT_NODE_HEIGHT, DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
import { useLanguage } from '@/composables/useLanguage'
import { useDiagramStore } from '@/stores'

// Vue Flow instance for viewport tracking and getting nodes with measured dimensions
const { viewport: vueFlowViewport, getViewport, getNodes } = useVueFlow()

// Diagram store for diagram type
const diagramStore = useDiagramStore()

// Current viewport - use Vue Flow's reactive viewport if available, otherwise poll
const viewport = computed(() => {
  // Vue Flow's viewport is reactive
  if (vueFlowViewport.value) {
    return vueFlowViewport.value
  }
  return getViewport()
})

// Only show for brace maps
const isBraceMap = computed(() => diagramStore.type === 'brace_map')

// Vue Flow adds measured/dimensions at runtime (not in base Node type)
// dimensions = user-resized via NodeResizer, measured = auto-measured by Vue Flow
interface NodeWithDimensions {
  measured?: { width?: number; height?: number }
  dimensions?: { width?: number; height?: number }
}

// Brace styling (per-group colors from mindmap palette, same as double bubble map)
const BRACE_STROKE_WIDTH = 2
const BRACE_TIP_SIZE = 2 // How far the pointy tip extends horizontally (compact)
const END_CURVE_SIZE = 5 // Size of curves at top/bottom ends (compact)

/**
 * Calculate brace groups from edges
 * Groups all children that share the same parent
 */
interface BraceGroup {
  parentId: string
  parentNode: { x: number; y: number; width: number; height: number }
  children: Array<{ id: string; x: number; y: number; width: number; height: number }>
}

const braceGroups = computed<BraceGroup[]>(() => {
  if (!isBraceMap.value) return []

  // Use Vue Flow's getNodes for measured dimensions
  // Use diagramStore.vueFlowEdges for edge data (Vue Flow edges are empty for brace maps)
  const nodes = getNodes.value
  const edges = diagramStore.vueFlowEdges

  // Build parent -> children map from edges
  const parentChildMap = new Map<string, string[]>()
  edges.forEach((edge) => {
    const children = parentChildMap.get(edge.source) || []
    children.push(edge.target)
    parentChildMap.set(edge.source, children)
  })

  // Helper to get node dimensions with NodeResizer-ready priority:
  // 1. node.dimensions (user-resized via NodeResizer)
  // 2. node.measured (auto-measured by Vue Flow)
  // 3. layoutConfig constants (fallback)
  const getNodeDimensions = (node: (typeof nodes)[0] & NodeWithDimensions) => {
    const width = node.dimensions?.width ?? node.measured?.width ?? DEFAULT_NODE_WIDTH
    const height = node.dimensions?.height ?? node.measured?.height ?? DEFAULT_NODE_HEIGHT
    return { width, height }
  }

  // Create brace groups
  const groups: BraceGroup[] = []

  parentChildMap.forEach((childIds, parentId) => {
    if (childIds.length === 0) return

    const parentNode = nodes.find((n) => n.id === parentId)
    if (!parentNode) return

    const parentDims = getNodeDimensions(parentNode)

    // Get children with their dimensions
    const children: BraceGroup['children'] = []
    for (const childId of childIds) {
      const childNode = nodes.find((n) => n.id === childId)
      if (!childNode) continue

      const childDims = getNodeDimensions(childNode)
      children.push({
        id: childNode.id,
        x: childNode.position.x,
        y: childNode.position.y,
        width: childDims.width,
        height: childDims.height,
      })
    }

    if (children.length === 0) return

    groups.push({
      parentId,
      parentNode: {
        x: parentNode.position.x,
        y: parentNode.position.y,
        width: parentDims.width,
        height: parentDims.height,
      },
      children,
    })
  })

  return groups
})

/**
 * Generate SVG path for a curly brace
 * Shape like: ╮
 *             |
 *             <  (pointy tip)
 *             |
 *             ╯
 * Small inward curves at top/bottom, vertical stem, pointy tip in middle
 */
function generateBracePath(group: BraceGroup): {
  bracePath: string
} {
  const parent = group.parentNode
  const children = group.children

  // Single child: straight horizontal line instead of a brace
  if (children.length === 1) {
    const child = children[0]
    const fromX = parent.x + parent.width
    const fromY = parent.y + parent.height / 2
    const toX = child.x
    const toY = child.y + child.height / 2
    return { bracePath: `M ${fromX} ${fromY} L ${toX} ${toY}` }
  }

  // Sort children by Y position
  const sortedChildren = [...children].sort((a, b) => a.y - b.y)

  // Calculate brace position
  const parentRightX = parent.x + parent.width

  // Find the vertical span of children
  const topChild = sortedChildren[0]
  const bottomChild = sortedChildren[sortedChildren.length - 1]
  const topY = topChild.y + topChild.height / 2
  const bottomY = bottomChild.y + bottomChild.height / 2

  // Brace tip aligns with the parent topic node's vertical center
  const tipY = parent.y + parent.height / 2

  // Brace X position (between parent and children)
  const childLeftX = Math.min(...children.map((c) => c.x))
  const braceX = (parentRightX + childLeftX) / 2

  // Curve parameters for the small hooks at top/bottom
  const curveSize = END_CURVE_SIZE
  // The vertical stem X position (where the curves connect to the stem)
  const stemX = braceX - curveSize
  // The pointy tip extends LEFT from the stem (toward parent)
  const tipX = stemX - BRACE_TIP_SIZE

  // Build the brace path - continuous path with V-tip indent:
  // 1. Top curve
  // 2. VERTICAL line down to V-start
  // 3. Diagonal to V-tip point (aligned with parent node's Y center)
  // 4. Diagonal from V-tip back
  // 5. VERTICAL line down
  // 6. Bottom curve
  //
  // Shape:  ╮
  //         |
  //          \
  //           < (tip aligned with parent topic)
  //          /
  //         |
  //         ╯
  const tipHeight = 4 // Half the V's vertical span (smaller = subtler tip)

  const bracePath = `
    M ${braceX} ${topY}
    Q ${stemX} ${topY} ${stemX} ${topY + curveSize}
    L ${stemX} ${tipY - tipHeight}
    L ${tipX} ${tipY}
    L ${stemX} ${tipY + tipHeight}
    L ${stemX} ${bottomY - curveSize}
    Q ${stemX} ${bottomY} ${braceX} ${bottomY}
  `.trim()

  return { bracePath }
}

/**
 * Generate SVG paths for each brace group with per-group colors
 */
const braceElements = computed(() => {
  const nodes = getNodes.value
  const targetIds = new Set(
    diagramStore.vueFlowEdges.map((e) => e.target)
  )
  const rootId = nodes.find((n) => !targetIds.has(n.id))?.id

  return braceGroups.value.map((group) => {
    const { bracePath } = generateBracePath(group)
    const isRootGroup = group.parentId === rootId
    const parentNode = nodes.find((n) => n.id === group.parentId)
    const groupIndex = isRootGroup
      ? 0
      : (parentNode?.data?.groupIndex as number | undefined) ?? 0
    const color = getMindmapBranchColor(groupIndex)
    return {
      groupId: group.parentId,
      bracePath,
      strokeColor: color.border,
    }
  })
})

// Alternative dimensions section (like archive brace-renderer.js lines 974-1027)
const { isZh } = useLanguage()
const SEPARATOR_OFFSET_Y = 15
const ALTERNATIVE_DIMENSIONS_OFFSET_Y = 15
const ALTERNATIVE_LABEL_FONT_SIZE = 13
const ALTERNATIVE_CHIP_FONT_SIZE = 12
const ALTERNATIVE_CHIP_COLOR = '#1976d2'

const alternativeDimensions = computed(() => {
  if (!isBraceMap.value) return []
  const diagramData = diagramStore.data
  if (diagramData && typeof diagramData === 'object' && 'alternative_dimensions' in diagramData) {
    const altDims = diagramData.alternative_dimensions
    if (Array.isArray(altDims)) {
      return altDims.filter((dim) => typeof dim === 'string' && dim.trim())
    }
  }
  return []
})

const alternativeDimensionsLabel = computed(() =>
  isZh.value ? '本主题的其他可能拆解维度：' : 'Other possible dimensions for this topic:'
)

/** Archive uses simple text "• dim1  • dim2" not individual chips */
const alternativeDimensionsChipsText = computed(() =>
  alternativeDimensions.value.map((d) => `• ${d}`).join('  ')
)

const braceMapSeparatorLine = computed(() => {
  if (!isBraceMap.value) return null
  const nodes = getNodes.value
  const treeNodes = nodes.filter((n) => n.type !== 'label' && n.id !== 'dimension-label')
  if (treeNodes.length === 0) return null

  const getNodeDimensions = (node: (typeof nodes)[0] & NodeWithDimensions) => ({
    width: node.dimensions?.width ?? node.measured?.width ?? DEFAULT_NODE_WIDTH,
    height: node.dimensions?.height ?? node.measured?.height ?? DEFAULT_NODE_HEIGHT,
  })

  let lowestBottom = 0
  let minX = Infinity
  let maxX = -Infinity
  treeNodes.forEach((node) => {
    const dims = getNodeDimensions(node)
    const bottom = node.position.y + dims.height
    if (bottom > lowestBottom) lowestBottom = bottom
    if (node.position.x < minX) minX = node.position.x
    if (node.position.x + dims.width > maxX) maxX = node.position.x + dims.width
  })
  if (minX === Infinity || maxX === -Infinity) return null

  const separatorY = lowestBottom + SEPARATOR_OFFSET_Y
  return { x1: minX, y1: separatorY, x2: maxX, y2: separatorY }
})

const braceMapAlternativePosition = computed(() => {
  if (!braceMapSeparatorLine.value) return null
  const labelY = braceMapSeparatorLine.value.y1 + ALTERNATIVE_DIMENSIONS_OFFSET_Y
  const chipsY = labelY + ALTERNATIVE_LABEL_FONT_SIZE + 8
  const centerX = (braceMapSeparatorLine.value.x1 + braceMapSeparatorLine.value.x2) / 2
  return { labelY, chipsY, centerX }
})

</script>

<template>
  <svg
    v-if="isBraceMap && (braceElements.length > 0 || braceMapSeparatorLine)"
    class="brace-overlay absolute inset-0 w-full h-full pointer-events-none"
    style="z-index: 0"
  >
    <g :transform="`translate(${viewport.x}, ${viewport.y}) scale(${viewport.zoom})`">
      <g
        v-for="element in braceElements"
        :key="element.groupId"
      >
        <!-- The curly brace -->
        <path
          :d="element.bracePath"
          :stroke="element.strokeColor"
          :stroke-width="BRACE_STROKE_WIDTH"
          fill="none"
          stroke-linecap="round"
          stroke-linejoin="miter"
          stroke-miterlimit="10"
        />
      </g>

      <!-- Alternative dimensions section (like archive brace-renderer.js - only when alternatives exist) -->
      <g
        v-if="
          alternativeDimensions.length > 0 &&
          braceMapSeparatorLine &&
          braceMapAlternativePosition
        "
      >
        <line
          :x1="braceMapSeparatorLine.x1"
          :y1="braceMapSeparatorLine.y1"
          :x2="braceMapSeparatorLine.x2"
          :y2="braceMapSeparatorLine.y2"
          :stroke="ALTERNATIVE_CHIP_COLOR"
          stroke-width="1"
          stroke-dasharray="4,4"
          :opacity="0.4"
          stroke-linecap="round"
        />
        <text
          :x="braceMapAlternativePosition.centerX"
          :y="braceMapAlternativePosition.labelY"
          :fill="ALTERNATIVE_CHIP_COLOR"
          :font-size="ALTERNATIVE_LABEL_FONT_SIZE"
          text-anchor="middle"
          dominant-baseline="middle"
          :opacity="0.7"
        >
          {{ alternativeDimensionsLabel }}
        </text>
        <text
          :x="braceMapAlternativePosition.centerX"
          :y="braceMapAlternativePosition.chipsY"
          :fill="ALTERNATIVE_CHIP_COLOR"
          :font-size="ALTERNATIVE_LABEL_FONT_SIZE - 1"
          text-anchor="middle"
          dominant-baseline="middle"
          font-weight="600"
          :opacity="0.8"
        >
          {{ alternativeDimensionsChipsText }}
        </text>
      </g>
    </g>
  </svg>
</template>

<style scoped>
.brace-overlay {
  overflow: visible;
}
</style>
