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

import { useLanguage } from '@/composables/core/useLanguage'
import { DEFAULT_NODE_HEIGHT, DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
import { useDiagramStore } from '@/stores'

// Vue Flow instance for viewport tracking and getting nodes with measured dimensions
const { viewport: vueFlowViewport, getViewport, getNodes } = useVueFlow()

// Diagram store for diagram type and spec metadata
const diagramStore = useDiagramStore()
const { t } = useLanguage()

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

const bridgePairs = computed<BridgePair[]>(() => {
  if (!isBridgeMap.value) return []

  // Use store's nodes for immediate reactivity, Vue Flow's getNodes for dimensions
  // This ensures the computed updates immediately when nodes are added/removed
  const storeNodes = diagramStore.data?.nodes || []

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

  // Helper to get node dimensions
  const getNodeDimensions = (node: (typeof nodes)[0] & NodeWithDimensions) => {
    const width = node.dimensions?.width ?? node.measured?.width ?? DEFAULT_NODE_WIDTH
    const height = node.dimensions?.height ?? node.measured?.height ?? DEFAULT_NODE_HEIGHT
    return { width, height }
  }

  // Group nodes by pairIndex
  const pairsMap = new Map<number, BridgePair>()

  nodes.forEach((node) => {
    // Check for pairIndex and position in node.data
    const rawPairIndex = node.data?.pairIndex
    const position = node.data?.position // 'left' or 'right'

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
    const nodeText =
      (node as { text?: string; data?: { label?: string } }).text ||
      (node as { text?: string; data?: { label?: string } }).data?.label ||
      ''
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
      const pair = pairsMap.get(pairIndex)
      if (!pair) {
        return
      }
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

  return pairs
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

  const centerY =
    bridgePairs.value.reduce((sum, pair) => {
      return (
        sum +
        (pair.leftNode.y + pair.leftNode.height / 2) +
        (pair.rightNode.y + pair.rightNode.height / 2)
      )
    }, 0) /
    (bridgePairs.value.length * 2)

  return { x1, y1: centerY, x2, y2: centerY }
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

const alternativeDimensionsLabel = computed(() =>
  t('diagram.alternativeDimensions.bridgeAnalogiesTitle')
)

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

/** Archive uses simple text "• dim1  • dim2" (slice 0-6 like archive) */
const alternativeDimensionsChipsText = computed(() => {
  const dims = alternativeDimensions.value.slice(0, 6)
  return dims.map((d) => `• ${d}`).join('  ')
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
    diagramStore.pushHistory(t('diagram.history.deleteAnalogyPair'))
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

    bridgeMapNodes.forEach((node) => {
      // Find the DOM element for this node
      const nodeElement = document.querySelector(`[data-id="${node.id}"]`) as HTMLElement
      if (!nodeElement) {
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

        <!-- Alternative dimensions text (archive format: "• dim1  • dim2") or placeholder -->
        <text
          v-if="alternativeDimensionsChipsText"
          :x="alternativeDimensionsPosition.centerX"
          :y="alternativeDimensionsPosition.chipsY"
          :fill="ALTERNATIVE_CHIP_COLOR"
          :font-size="ALTERNATIVE_CHIP_FONT_SIZE"
          font-weight="600"
          :opacity="0.8"
          text-anchor="middle"
          dominant-baseline="middle"
        >
          {{ alternativeDimensionsChipsText }}
        </text>
        <text
          v-else
          :x="alternativeDimensionsPosition.centerX"
          :y="alternativeDimensionsPosition.chipsY"
          :fill="ALTERNATIVE_CHIP_COLOR"
          :font-size="ALTERNATIVE_CHIP_FONT_SIZE"
          :opacity="0.4"
          font-style="italic"
          text-anchor="middle"
          dominant-baseline="middle"
        >
          {{ t('diagram.bridgeMap.alternativesEmpty') }}
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
  transition:
    opacity 0.2s ease,
    transform 0.15s ease;
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
