<script setup lang="ts">
/**
 * BridgeOverlay - Draws bridge map visual elements
 * - Vertical lines connecting left and right nodes in each analogy pair
 * - Triangle separators between pairs
 * - Dimension label on the left side
 * - Hover selection box with delete button for analogy pairs
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { DEFAULT_NODE_HEIGHT, DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
import { useDiagramStore } from '@/stores'

// Helper function to get timestamp for logging
function getTimestamp(): string {
  return new Date().toISOString()
}

// Vue Flow instance for viewport tracking and getting nodes with measured dimensions
const { viewport: vueFlowViewport, getViewport, getNodes } = useVueFlow()

// Diagram store for diagram type and spec metadata
const diagramStore = useDiagramStore()

// Hover state for pairs
const hoveredPairIndex = ref<number | null>(null)

// Store event handlers for cleanup
const nodeEventHandlers = new Map<string, { mouseenter: () => void; mouseleave: () => void }>()

// Current viewport - use Vue Flow's reactive viewport if available, otherwise poll
const viewport = computed(() => {
  // Vue Flow's viewport is reactive
  if (vueFlowViewport.value) {
    return vueFlowViewport.value
  }
  return getViewport()
})

// Only show for bridge maps
const isBridgeMap = computed(() => diagramStore.type === 'bridge_map')

// Vue Flow adds measured/dimensions at runtime (not in base Node type)
interface NodeWithDimensions {
  measured?: { width?: number; height?: number }
  dimensions?: { width?: number; height?: number }
}

// Bridge styling
const BRIDGE_LINE_COLOR = '#666' // Darker grey for horizontal bridge line (matching old JS)
const BRIDGE_LINE_WIDTH = 2
const TRIANGLE_COLOR = '#666' // Darker grey for triangle separators (matching old JS)
const TRIANGLE_HEIGHT = 8 // Height of triangle separator (vertical distance from base to tip)
const TRIANGLE_BASE_WIDTH = 12 // Width of triangle base (bottom edge)
const DIMENSION_LABEL_COLOR = '#303133' // Dark gray for dimension label
const DIMENSION_FONT_SIZE = 14
const DIMENSION_LABEL_X = 50 // X position for dimension label (left side)
const AS_LABEL_COLOR = '#606266' // Grey for "as" labels
const AS_LABEL_FONT_SIZE = 12
const AS_LABEL_OFFSET_Y = 15 // Distance below triangle
const SEPARATOR_COLOR = '#1976d2' // Same blue as alternative dimensions text
const SEPARATOR_OPACITY = 0.4
const SEPARATOR_OFFSET_Y = 15 // Distance below lowest node
const SEPARATOR_DASHARRAY = '4,4' // Dashed line pattern
const ALTERNATIVE_DIMENSIONS_OFFSET_Y = 15 // Distance below separator line
const ALTERNATIVE_LABEL_FONT_SIZE = 13
const ALTERNATIVE_CHIP_FONT_SIZE = 12
const ALTERNATIVE_CHIP_COLOR = '#1976d2' // Dark blue
const ALTERNATIVE_CHIP_OPACITY = 0.8
const ALTERNATIVE_CHIP_SPACING = 8 // Horizontal spacing between chips
const ALTERNATIVE_CHIP_PADDING_X = 8 // Horizontal padding inside chip
const ALTERNATIVE_CHIP_PADDING_Y = 4 // Vertical padding inside chip
const ALTERNATIVE_CHIP_RADIUS = 4 // Border radius for chips
const DELETE_BUTTON_SIZE = 24 // Size of delete button
const DELETE_BUTTON_OFFSET_X = 6 // Horizontal offset from right edge
const DELETE_BUTTON_OFFSET_Y = 6 // Vertical offset from top

/**
 * Get bridge map pairs from nodes
 * Groups nodes into pairs based on pairIndex
 */
interface BridgePair {
  pairIndex: number
  leftNode: { id: string; x: number; y: number; width: number; height: number; text: string }
  rightNode: { id: string; x: number; y: number; width: number; height: number; text: string }
}

// Track node count to force recalculation when nodes change
const bridgeMapNodeCount = computed(() => {
  if (!isBridgeMap.value || !diagramStore.data?.nodes) return 0
  return diagramStore.data.nodes.filter(
    (n) =>
      n.data?.diagramType === 'bridge_map' &&
      n.data?.pairIndex !== undefined &&
      !n.data?.isDimensionLabel
  ).length
})

const bridgePairs = computed<BridgePair[]>(() => {
  if (!isBridgeMap.value) return []

  // Force dependency on node count to ensure recalculation when nodes are added/removed
  const nodeCount = bridgeMapNodeCount.value
  
  // Also depend on the actual nodes array length to ensure reactivity
  const nodesLength = diagramStore.data?.nodes?.length || 0

  // Use store's nodes for immediate reactivity, Vue Flow's getNodes for dimensions
  // This ensures the computed updates immediately when nodes are added/removed
  const storeNodes = diagramStore.data?.nodes || []
  
  // Force dependency on store nodes array to ensure reactivity
  // Create a string key from node IDs to force recalculation when nodes change
  const nodesKey = storeNodes.map((n) => n.id).join(',')
  
  const vueFlowNodes = getNodes.value
  
  // Create a map of Vue Flow nodes by ID for dimension lookup
  const vueFlowNodesMap = new Map(vueFlowNodes.map((node) => [node.id, node]))
  
  // Use store nodes as the source of truth, but get dimensions and positions from Vue Flow
  // Vue Flow positions are more accurate after nodes are moved or layout is recalculated
  const nodes = storeNodes.map((storeNode) => {
    const vueFlowNode = vueFlowNodesMap.get(storeNode.id)
    const vueFlowMeasured = vueFlowNode
      ? (vueFlowNode as { measured?: { width?: number; height?: number } }).measured
      : undefined
    return {
      ...storeNode,
      // Use Vue Flow's position if available (more accurate after moves/layout changes)
      position: vueFlowNode?.position || storeNode.position,
      // Merge Vue Flow's measured dimensions if available
      measured: vueFlowMeasured,
      dimensions: vueFlowNode?.dimensions,
    }
  })
  
  // Debug: log when nodes change
  if (isBridgeMap.value && nodesKey) {
    console.debug(`[BridgeOverlay] [${getTimestamp()}] bridgePairs recalculating:`, {
      nodesKey,
      storeNodesCount: storeNodes.length,
      vueFlowNodesCount: vueFlowNodes.length,
      bridgeMapNodes: storeNodes.filter((n) => n.data?.diagramType === 'bridge_map').length,
    })
  }

  // Helper to get node dimensions
  const getNodeDimensions = (node: (typeof nodes)[0] & NodeWithDimensions) => {
    const width =
      node.dimensions?.width ?? node.measured?.width ?? DEFAULT_NODE_WIDTH
    const height =
      node.dimensions?.height ?? node.measured?.height ?? DEFAULT_NODE_HEIGHT
    return { width, height }
  }

  // Group nodes by pairIndex
  const pairsMap = new Map<number, BridgePair>()

  nodes.forEach((node) => {
    // Check for pairIndex and position in node.data
    const rawPairIndex = node.data?.pairIndex
    const position = node.data?.position // 'left' or 'right'

    // Debug: log nodes that don't have pairIndex/position
    if (isBridgeMap.value && rawPairIndex === undefined && node.data?.diagramType === 'bridge_map') {
      console.debug(`[BridgeOverlay] [${getTimestamp()}] Node missing pairIndex:`, node.id, node.data)
    }

    if (
      rawPairIndex === undefined ||
      rawPairIndex === null ||
      typeof rawPairIndex !== 'number' ||
      !position
    ) {
      return
    }

    const pairIndex = rawPairIndex as number
    const pos = node.position ?? { x: 0, y: 0 }

    const dims = getNodeDimensions(node)
    // Get text from node.text (DiagramNode) or node.data.label (Vue Flow node)
    const nodeText = (node as { text?: string; data?: { label?: string } }).text ||
                     (node as { text?: string; data?: { label?: string } }).data?.label || ''
    const nodeInfo = {
      id: node.id,
      x: pos.x,
      y: pos.y,
      width: dims.width,
      height: dims.height,
      text: nodeText,
    }

    if (!pairsMap.has(pairIndex)) {
      pairsMap.set(pairIndex, {
        pairIndex,
        leftNode: position === 'left' ? nodeInfo : ({} as BridgePair['leftNode']),
        rightNode: position === 'right' ? nodeInfo : ({} as BridgePair['rightNode']),
      })
    } else {
      const pair = pairsMap.get(pairIndex)!
      if (position === 'left') {
        pair.leftNode = nodeInfo
      } else {
        pair.rightNode = nodeInfo
      }
    }
  })

  // Convert map to array and sort by pairIndex
  const pairs = Array.from(pairsMap.values())
    .filter((pair) => pair.leftNode.id && pair.rightNode.id)
    .sort((a, b) => a.pairIndex - b.pairIndex)

  // Debug: log detected pairs with detailed position info
  if (isBridgeMap.value && pairs.length > 0) {
    console.debug(`[BridgeOverlay] [${getTimestamp()}] Detected pairs:`, {
      count: pairs.length,
      pairs: pairs.map((p) => ({
        pairIndex: p.pairIndex,
        leftNode: {
          id: p.leftNode.id,
          x: p.leftNode.x,
          width: p.leftNode.width,
          rightEdge: p.leftNode.x + p.leftNode.width,
        },
        rightNode: {
          id: p.rightNode.id,
          x: p.rightNode.x,
          width: p.rightNode.width,
          rightEdge: p.rightNode.x + p.rightNode.width,
        },
      })),
      pairIndices: pairs.map((p) => p.pairIndex),
    })
  }

  return pairs
})

/**
 * Get dimension label from label node (if exists) or spec metadata
 */
const dimensionLabel = computed(() => {
  if (!isBridgeMap.value) return ''
  
  // First check if there's a dimension label node
  const nodes = getNodes.value
  const labelNode = nodes.find((node) => node.id === 'dimension-label')
  if (labelNode?.data?.label) {
    return labelNode.data.label
  }
  
  // Fallback: Try to get dimension from diagram data (spec metadata is preserved there)
  const diagramData = diagramStore.data
  if (diagramData && typeof diagramData === 'object') {
    // Check for dimension field
    if ('dimension' in diagramData) {
      const dim = diagramData.dimension
      if (typeof dim === 'string' && dim.trim()) {
        return dim
      }
    }
    
    // Fallback to relating_factor if dimension is not available
    if ('relating_factor' in diagramData) {
      const rf = diagramData.relating_factor
      if (typeof rf === 'string' && rf.trim()) {
        return rf
      }
    }
  }
  
  return ''
})

/**
 * Calculate horizontal bridge line that spans across all pairs
 */
const horizontalBridgeLine = computed(() => {
  if (bridgePairs.value.length === 0) return null

  const firstPair = bridgePairs.value[0]
  const lastPair = bridgePairs.value[bridgePairs.value.length - 1]

  const x1 = firstPair.leftNode.x
  const lastPairWidth = Math.max(lastPair.leftNode.width, lastPair.rightNode.width)
  const x2 = lastPair.leftNode.x + lastPairWidth

  const centerY = bridgePairs.value.reduce((sum, pair) => {
    return sum + (pair.leftNode.y + pair.leftNode.height / 2) + (pair.rightNode.y + pair.rightNode.height / 2)
  }, 0) / (bridgePairs.value.length * 2)

  const result = { x1, y1: centerY, x2, y2: centerY }
  
  if (isBridgeMap.value) {
    console.debug(`[BridgeOverlay] [${getTimestamp()}] horizontalBridgeLine calculated:`, {
      pairsCount: bridgePairs.value.length,
      x1: result.x1,
      x2: result.x2,
      width: result.x2 - result.x1,
      y1: result.y1,
      firstPairIndex: firstPair.pairIndex,
      lastPairIndex: lastPair.pairIndex,
    })
  }

  return result
})

/**
 * Calculate triangle separator positions between pairs
 * Triangles are positioned on the horizontal bridge line
 */
const triangleSeparators = computed(() => {
  if (!horizontalBridgeLine.value) return []

  const triangles: Array<{
    x: number
    y: number
    pairIndex: number
    asLabelY: number // Y position for "as" label below triangle
  }> = []

  const bridgeY = horizontalBridgeLine.value.y1

  for (let i = 0; i < bridgePairs.value.length - 1; i++) {
    const currentPair = bridgePairs.value[i]
    const nextPair = bridgePairs.value[i + 1]

    // Triangle positioned at the midpoint between pairs, on the bridge line
    const currentRightX = currentPair.rightNode.x + currentPair.rightNode.width
    const nextLeftX = nextPair.leftNode.x
    const triangleX = (currentRightX + nextLeftX) / 2

    triangles.push({
      x: triangleX,
      y: bridgeY,
      pairIndex: i,
      asLabelY: bridgeY + AS_LABEL_OFFSET_Y, // Position "as" label below triangle
    })
  }

  return triangles
})

/**
 * Get "as" label text (always "as" regardless of language)
 */
const asLabelText = computed(() => {
  return 'as'
})

/**
 * Detect if diagram contains Chinese characters
 */
const hasChineseContent = computed(() => {
  const nodes = getNodes.value
  return nodes.some((node) => {
    const text = node.data?.label || ''
    return /[\u4e00-\u9fa5]/.test(text)
  })
})

/**
 * Get alternative dimensions from diagram store metadata
 */
const alternativeDimensions = computed(() => {
  if (!isBridgeMap.value) return []
  
  const diagramData = diagramStore.data
  if (diagramData && typeof diagramData === 'object' && 'alternative_dimensions' in diagramData) {
    const altDims = diagramData.alternative_dimensions
    if (Array.isArray(altDims)) {
      return altDims.filter((dim) => typeof dim === 'string' && dim.trim())
    }
  }
  
  return []
})

/**
 * Get alternative dimensions label text (language-aware)
 */
const alternativeDimensionsLabel = computed(() => {
  return hasChineseContent.value
    ? '本主题的其他可能类比关系:'
    : 'Other possible analogy relationships:'
})

/**
 * Calculate alternative dimensions section position
 */
const alternativeDimensionsPosition = computed(() => {
  if (!separatorLine.value) return null

  const labelY = separatorLine.value.y1 + ALTERNATIVE_DIMENSIONS_OFFSET_Y
  const chipsY = labelY + ALTERNATIVE_LABEL_FONT_SIZE + 8 // 8px gap between label and chips

  // Calculate center X based on content width
  const centerX = (separatorLine.value.x1 + separatorLine.value.x2) / 2

  return {
    labelY,
    chipsY,
    centerX,
  }
})

/**
 * Calculate chip positions for alternative dimensions
 */
const alternativeDimensionChips = computed(() => {
  const dims = alternativeDimensions.value
  if (dims.length === 0) return []
  
  if (!alternativeDimensionsPosition.value) return []

  const { centerX, chipsY } = alternativeDimensionsPosition.value
  
  // Estimate chip widths (rough approximation)
  const chipWidths = dims.map((dim) => {
    // Approximate: 8px padding * 2 + text width (rough estimate: 8px per character)
    return ALTERNATIVE_CHIP_PADDING_X * 2 + dim.length * 8
  })

  // Calculate total width and starting X
  const totalWidth = chipWidths.reduce((sum, w) => sum + w, 0) + ALTERNATIVE_CHIP_SPACING * (dims.length - 1)
  let currentX = centerX - totalWidth / 2

  return dims.map((dim, index) => {
    const chipX = currentX + chipWidths[index] / 2
    currentX += chipWidths[index] + ALTERNATIVE_CHIP_SPACING
    
    return {
      text: dim,
      x: chipX,
      y: chipsY,
      width: chipWidths[index],
    }
  })
})

/**
 * Calculate dimension label position from label node (if exists)
 * Otherwise calculate from bridge pairs
 */
const dimensionLabelPosition = computed(() => {
  // First try to get position from dimension label node
  const nodes = getNodes.value
  
  // Helper to get node dimensions (redefined here for use in this computed)
  const getNodeDimensions = (node: (typeof nodes)[0] & NodeWithDimensions) => {
    const width =
      node.dimensions?.width ?? node.measured?.width ?? DEFAULT_NODE_WIDTH
    const height =
      node.dimensions?.height ?? node.measured?.height ?? DEFAULT_NODE_HEIGHT
    return { width, height }
  }
  
  const labelNode = nodes.find((node) => node.id === 'dimension-label')
  if (labelNode) {
    const dims = getNodeDimensions(labelNode as (typeof nodes)[0] & NodeWithDimensions)
    return {
      x: labelNode.position.x,
      y: labelNode.position.y + dims.height / 2, // Center vertically
    }
  }

  // Fallback: calculate from bridge pairs
  if (bridgePairs.value.length === 0) return null

  // Find the vertical span of all pairs
  const allYPositions: number[] = []
  bridgePairs.value.forEach((pair) => {
    allYPositions.push(pair.leftNode.y)
    allYPositions.push(pair.rightNode.y + pair.rightNode.height)
  })

  const minY = Math.min(...allYPositions)
  const maxY = Math.max(...allYPositions)
  const centerY = (minY + maxY) / 2

  return {
    x: DIMENSION_LABEL_X,
    y: centerY,
  }
})

/**
 * Calculate dashed separator line position (below bridge map)
 */
const separatorLine = computed(() => {
  if (bridgePairs.value.length === 0) return null

  // Find the bottom edge of the lowest node
  const allBottomEdges: number[] = []
  bridgePairs.value.forEach((pair) => {
    allBottomEdges.push(pair.leftNode.y + pair.leftNode.height)
    allBottomEdges.push(pair.rightNode.y + pair.rightNode.height)
  })

  const lowestBottom = Math.max(...allBottomEdges)
  const separatorY = lowestBottom + SEPARATOR_OFFSET_Y

  // Find the leftmost and rightmost content edges
  const allXPositions: number[] = []
  bridgePairs.value.forEach((pair) => {
    allXPositions.push(pair.leftNode.x)
    allXPositions.push(pair.rightNode.x)
    allXPositions.push(pair.leftNode.x + pair.leftNode.width)
    allXPositions.push(pair.rightNode.x + pair.rightNode.width)
  })

  const minX = Math.min(...allXPositions)
  const maxX = Math.max(...allXPositions)

  return {
    x1: minX,
    y1: separatorY,
    x2: maxX,
    y2: separatorY,
  }
})

/**
 * Calculate delete button positions for each pair
 */
const pairDeleteButtons = computed(() => {
  return bridgePairs.value.map((pair) => {
    const maxX = Math.max(
      pair.leftNode.x + pair.leftNode.width,
      pair.rightNode.x + pair.rightNode.width
    )
    const minY = Math.min(pair.leftNode.y, pair.rightNode.y)

    // Position delete button at top right of the pair
    return {
      pairIndex: pair.pairIndex,
      deleteButtonX: maxX - DELETE_BUTTON_OFFSET_X,
      deleteButtonY: minY - DELETE_BUTTON_OFFSET_Y,
    }
  })
})


/**
 * Handle pair hover leave with delay to prevent flickering
 */
let hoverLeaveTimeout: ReturnType<typeof setTimeout> | null = null

function handlePairMouseLeave() {
  // Add a small delay before hiding to prevent flickering when moving to delete button
  hoverLeaveTimeout = setTimeout(() => {
    hoveredPairIndex.value = null
    hoverLeaveTimeout = null
  }, 100)
}

function handlePairMouseEnter(pairIndex: number) {
  // Clear any pending leave timeout
  if (hoverLeaveTimeout) {
    clearTimeout(hoverLeaveTimeout)
    hoverLeaveTimeout = null
  }
  console.debug(`[BridgeOverlay] Pair ${pairIndex} hovered`)
  hoveredPairIndex.value = pairIndex
}

function handleDeleteButtonMouseEnter(pairIndex: number) {
  // Clear any pending leave timeout when hovering over delete button
  if (hoverLeaveTimeout) {
    clearTimeout(hoverLeaveTimeout)
    hoverLeaveTimeout = null
  }
  hoveredPairIndex.value = pairIndex
}

/**
 * Handle delete button click
 */
function handleDeletePair(pairIndex: number, event: MouseEvent) {
  event.stopPropagation()
  const leftNodeId = `pair-${pairIndex}-left`
  const rightNodeId = `pair-${pairIndex}-right`

  // Delete both nodes
  if (diagramStore.removeNode(leftNodeId) && diagramStore.removeNode(rightNodeId)) {
    diagramStore.pushHistory('删除类比对')
    hoveredPairIndex.value = null
  }
}

/**
 * Attach mouse event listeners to bridge map nodes
 */
function attachNodeListeners() {
  if (!isBridgeMap.value) return

  nextTick(() => {
    const nodes = getNodes.value
    const bridgeMapNodes = nodes.filter(
      (node) =>
        node.data?.diagramType === 'bridge_map' &&
        node.data?.pairIndex !== undefined &&
        !node.data?.isDimensionLabel
    )

    console.debug(`[BridgeOverlay] Attaching listeners to ${bridgeMapNodes.length} bridge map nodes`)

    bridgeMapNodes.forEach((node) => {
      // Find the DOM element for this node
      const nodeElement = document.querySelector(`[data-id="${node.id}"]`) as HTMLElement
      if (!nodeElement) {
        console.debug(`[BridgeOverlay] Node element not found for ${node.id}`)
        return
      }

      const pairIndex = node.data?.pairIndex as number
      if (pairIndex === undefined) return

      // Remove existing listeners if any
      const existingHandlers = nodeEventHandlers.get(node.id)
      if (existingHandlers) {
        nodeElement.removeEventListener('mouseenter', existingHandlers.mouseenter)
        nodeElement.removeEventListener('mouseleave', existingHandlers.mouseleave)
      }

      // Create new handlers
      const mouseenterHandler = () => handlePairMouseEnter(pairIndex)
      const mouseleaveHandler = handlePairMouseLeave

      // Store handlers for cleanup
      nodeEventHandlers.set(node.id, {
        mouseenter: mouseenterHandler,
        mouseleave: mouseleaveHandler,
      })

      // Add new listeners
      nodeElement.addEventListener('mouseenter', mouseenterHandler)
      nodeElement.addEventListener('mouseleave', mouseleaveHandler)
      console.debug(`[BridgeOverlay] Attached listeners to node ${node.id} (pair ${pairIndex})`)
    })
  })
}

// Watch for node changes and reattach listeners
watch(
  () => [bridgePairs.value.length, getNodes.value.length],
  () => {
    if (isBridgeMap.value) {
      attachNodeListeners()
    }
  },
  { immediate: true }
)

onMounted(() => {
  if (isBridgeMap.value) {
    // Delay to ensure nodes are rendered
    setTimeout(() => {
      attachNodeListeners()
    }, 100)
  }
})

onUnmounted(() => {
  // Clean up listeners
  nodeEventHandlers.forEach((handlers, nodeId) => {
    const nodeElement = document.querySelector(`[data-id="${nodeId}"]`) as HTMLElement
    if (nodeElement) {
      nodeElement.removeEventListener('mouseenter', handlers.mouseenter)
      nodeElement.removeEventListener('mouseleave', handlers.mouseleave)
    }
  })
  nodeEventHandlers.clear()
  
  // Clear any pending timeout
  if (hoverLeaveTimeout) {
    clearTimeout(hoverLeaveTimeout)
    hoverLeaveTimeout = null
  }
})
</script>

<template>
  <svg
    v-if="isBridgeMap && bridgePairs.length > 0"
    class="bridge-overlay absolute inset-0 w-full h-full"
    style="z-index: 100"
  >
    <g :transform="`translate(${viewport.x}, ${viewport.y}) scale(${viewport.zoom})`">
      <!-- Horizontal bridge line spanning across all pairs -->
      <line
        v-if="horizontalBridgeLine"
        :key="`bridge-line-${bridgePairs.length}-${horizontalBridgeLine.x1}-${horizontalBridgeLine.x2}`"
        :x1="horizontalBridgeLine.x1"
        :y1="horizontalBridgeLine.y1"
        :x2="horizontalBridgeLine.x2"
        :y2="horizontalBridgeLine.y2"
        :stroke="BRIDGE_LINE_COLOR"
        :stroke-width="BRIDGE_LINE_WIDTH"
        stroke-linecap="round"
      />

      <!-- Triangle separators between pairs (pointing up) -->
      <polygon
        v-for="triangle in triangleSeparators"
        :key="`triangle-${triangle.pairIndex}`"
        :points="`${triangle.x - TRIANGLE_BASE_WIDTH / 2},${triangle.y} ${triangle.x + TRIANGLE_BASE_WIDTH / 2},${triangle.y} ${triangle.x},${triangle.y - TRIANGLE_HEIGHT}`"
        :fill="TRIANGLE_COLOR"
        :stroke="TRIANGLE_COLOR"
        stroke-width="1"
      />

      <!-- "as" labels below each triangle -->
      <text
        v-for="triangle in triangleSeparators"
        :key="`as-label-${triangle.pairIndex}`"
        :x="triangle.x"
        :y="triangle.asLabelY"
        :fill="AS_LABEL_COLOR"
        :font-size="AS_LABEL_FONT_SIZE"
        text-anchor="middle"
        dominant-baseline="middle"
        class="as-label"
      >
        {{ asLabelText }}
      </text>

      <!-- Dashed separator line below bridge map -->
      <line
        v-if="separatorLine"
        :x1="separatorLine.x1"
        :y1="separatorLine.y1"
        :x2="separatorLine.x2"
        :y2="separatorLine.y2"
        :stroke="SEPARATOR_COLOR"
        :stroke-width="BRIDGE_LINE_WIDTH"
        :stroke-dasharray="SEPARATOR_DASHARRAY"
        :opacity="SEPARATOR_OPACITY"
        stroke-linecap="round"
      />

      <!-- Alternative dimensions section (always visible) -->
      <g v-if="separatorLine && alternativeDimensionsPosition">
        <!-- Label text -->
        <text
          :x="alternativeDimensionsPosition.centerX"
          :y="alternativeDimensionsPosition.labelY"
          :fill="ALTERNATIVE_CHIP_COLOR"
          :font-size="ALTERNATIVE_LABEL_FONT_SIZE"
          :opacity="ALTERNATIVE_CHIP_OPACITY"
          text-anchor="middle"
          dominant-baseline="middle"
          class="alternative-label"
        >
          {{ alternativeDimensionsLabel }}
        </text>

        <!-- Chips for alternative dimensions -->
        <template v-if="alternativeDimensionChips.length > 0">
          <g
            v-for="(chip, index) in alternativeDimensionChips"
            :key="`chip-${index}`"
          >
            <!-- Chip background (rounded rectangle) -->
            <rect
              :x="chip.x - chip.width / 2"
              :y="chip.y - ALTERNATIVE_CHIP_PADDING_Y - ALTERNATIVE_CHIP_FONT_SIZE / 2"
              :width="chip.width"
              :height="ALTERNATIVE_CHIP_FONT_SIZE + ALTERNATIVE_CHIP_PADDING_Y * 2"
              :rx="ALTERNATIVE_CHIP_RADIUS"
              :fill="ALTERNATIVE_CHIP_COLOR"
              :opacity="ALTERNATIVE_CHIP_OPACITY"
            />
            <!-- Chip text -->
            <text
              :x="chip.x"
              :y="chip.y"
              fill="white"
              :font-size="ALTERNATIVE_CHIP_FONT_SIZE"
              text-anchor="middle"
              dominant-baseline="middle"
              class="alternative-chip-text"
            >
              {{ chip.text }}
            </text>
          </g>
        </template>

        <!-- Placeholder text when no alternative dimensions -->
        <text
          v-else
          :x="alternativeDimensionsPosition.centerX"
          :y="alternativeDimensionsPosition.chipsY"
          :fill="ALTERNATIVE_CHIP_COLOR"
          :font-size="ALTERNATIVE_CHIP_FONT_SIZE"
          :opacity="0.6"
          text-anchor="middle"
          dominant-baseline="middle"
          class="alternative-placeholder"
        >
          {{ hasChineseContent ? '[替代关系将在此显示]' : '[Alternative relationships will be displayed here]' }}
        </text>
      </g>

      <!-- Dimension label is now rendered as a LabelNode, so we don't need to draw it here -->

      <!-- Delete buttons for analogy pairs -->
      <g
        v-for="button in pairDeleteButtons"
        :key="`pair-delete-${button.pairIndex}`"
        class="pair-hover-group"
      >
        <!-- Delete button (shown on hover) -->
        <g
          v-if="hoveredPairIndex === button.pairIndex"
          class="pair-delete-button"
          :transform="`translate(${button.deleteButtonX}, ${button.deleteButtonY})`"
          @mouseenter="handleDeleteButtonMouseEnter(button.pairIndex)"
          @mouseleave="handlePairMouseLeave"
          @click="handleDeletePair(button.pairIndex, $event)"
        >
          <!-- Button background circle -->
          <circle
            :r="DELETE_BUTTON_SIZE / 2"
            fill="#ef4444"
            :opacity="0.9"
            class="delete-button-bg"
          />
          <!-- X icon -->
          <g
            :transform="`translate(${-DELETE_BUTTON_SIZE / 2}, ${-DELETE_BUTTON_SIZE / 2})`"
            fill="white"
            stroke="white"
            stroke-width="2"
            stroke-linecap="round"
          >
            <line
              :x1="DELETE_BUTTON_SIZE * 0.3"
              :y1="DELETE_BUTTON_SIZE * 0.3"
              :x2="DELETE_BUTTON_SIZE * 0.7"
              :y2="DELETE_BUTTON_SIZE * 0.7"
            />
            <line
              :x1="DELETE_BUTTON_SIZE * 0.7"
              :y1="DELETE_BUTTON_SIZE * 0.3"
              :x2="DELETE_BUTTON_SIZE * 0.3"
              :y2="DELETE_BUTTON_SIZE * 0.7"
            />
          </g>
        </g>
      </g>
    </g>
  </svg>
</template>

<style scoped>
.bridge-overlay {
  overflow: visible;
  pointer-events: none;
}

.dimension-label {
  user-select: none;
}

/* Enable pointer events for buttons */
.pair-hover-group {
  pointer-events: none;
}

.pair-delete-button {
  cursor: pointer;
  pointer-events: all;
}

.pair-delete-button circle {
  pointer-events: all;
}

.delete-button-bg {
  transition: opacity 0.2s ease, transform 0.15s ease;
  cursor: pointer;
}

.pair-delete-button:hover .delete-button-bg {
  opacity: 1;
  transform: scale(1.1);
}

.pair-delete-button:active .delete-button-bg {
  transform: scale(0.95);
}

/* Smooth fade in/out for delete button group */
.pair-delete-button {
  transition: opacity 0.2s ease;
  opacity: 0.8;
}

.pair-delete-button:hover {
  opacity: 1;
}
</style>
