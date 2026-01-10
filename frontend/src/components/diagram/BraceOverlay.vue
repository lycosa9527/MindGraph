<script setup lang="ts">
/**
 * BraceOverlay - Draws proper curly braces for brace maps
 * Creates unified brace shapes connecting parents to their children groups
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

import { DEFAULT_NODE_HEIGHT, DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
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

// Brace styling
const BRACE_COLOR = '#64748b' // Tailwind slate-500 (matches the screenshot)
const BRACE_STROKE_WIDTH = 2
const BRACE_TIP_SIZE = 6 // How far the pointy tip extends horizontally
const END_CURVE_SIZE = 12 // Size of curves at top/bottom ends

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
    const width =
      node.dimensions?.width ?? node.measured?.width ?? DEFAULT_NODE_WIDTH
    const height =
      node.dimensions?.height ?? node.measured?.height ?? DEFAULT_NODE_HEIGHT
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
 * Generate SVG paths for each brace group
 */
const braceElements = computed(() => {
  return braceGroups.value.map((group) => {
    const { bracePath } = generateBracePath(group)
    return {
      groupId: group.parentId,
      bracePath,
    }
  })
})
</script>

<template>
  <svg
    v-if="isBraceMap && braceElements.length > 0"
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
          :stroke="BRACE_COLOR"
          :stroke-width="BRACE_STROKE_WIDTH"
          fill="none"
          stroke-linecap="round"
          stroke-linejoin="miter"
          stroke-miterlimit="10"
        />
      </g>
    </g>
  </svg>
</template>

<style scoped>
.brace-overlay {
  overflow: visible;
}
</style>
