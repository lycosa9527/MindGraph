<script setup lang="ts">
/**
 * LabelNode - Text label node for dimension labels and annotations
 * Tree Maps: classification dimension (分类维度); Brace Maps: decomposition dimension (拆解维度)
 * Supports inline text editing on double-click
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { CSSProperties } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { eventBus } from '@/composables/core/useEventBus'
import { translateDimension, useLanguage } from '@/composables/core/useLanguage'
import { BRANCH_NODE_HEIGHT } from '@/composables/diagrams/layoutConfig'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { useDiagramStore, useUIStore } from '@/stores'
import type { MindGraphNodeProps } from '@/types'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const { t } = useLanguage()
const uiStore = useUIStore()
const isPlaceholder = computed(() => props.data.isPlaceholder || !props.data.label)
const isBridgeDimension = computed(
  () => props.data.diagramType === 'bridge_map' && props.data.isDimensionLabel
)

// Position recalculation for bridge map dimension labels
const labelRef = ref<HTMLElement | null>(null)
useNodeDimensions(labelRef, props.id)
const { getNodes, updateNode } = useVueFlow()
const diagramStore = useDiagramStore()
let resizeObserver: ResizeObserver | null = null

// Recalculate position when text changes to prevent overlap and maintain vertical centering
async function recalculatePosition() {
  if (!isBridgeDimension.value || !labelRef.value) return

  // Get label node and measure its actual dimensions
  const nodes = getNodes.value
  const labelNode = nodes.find((node) => node.id === props.id)
  if (!labelNode) return

  const labelElement = labelRef.value
  const maxWidth = 180 // Max width from CSS (max-width: 180px)
  // Measure actual height (changes when text wraps)
  const actualHeight = labelElement.offsetHeight || 40 // Fallback to estimate
  // Measure actual width instead of using maxWidth for overlap detection
  const actualWidth = labelElement.offsetWidth || maxWidth

  // For overlap detection, use actual width if available, otherwise maxWidth
  const labelX = labelNode.position.x
  const labelRightEdge = labelX + actualWidth

  console.log('[LabelNode-recalculatePosition] Starting recalculation:', {
    labelX,
    labelRightEdge,
    actualWidth,
    maxWidth,
    actualHeight,
  })

  // Get all bridge map nodes (excluding the label itself)
  const bridgeNodes = nodes.filter(
    (node) =>
      node.data?.diagramType === 'bridge_map' &&
      node.id !== props.id &&
      node.data?.pairIndex !== undefined
  )

  if (bridgeNodes.length === 0) {
    console.log('[LabelNode-recalculatePosition] No bridge nodes found, skipping')
    return
  }

  // Find the leftmost node
  const leftmostNode = bridgeNodes.reduce((leftmost, node) => {
    if (!leftmost) return node
    return node.position.x < leftmost.position.x ? node : leftmost
  }, bridgeNodes[0])

  const leftmostX = leftmostNode.position.x
  // Gap from label's right edge to node's left edge (should be 10px)
  const gapFromLabelRight = 10

  console.log('[LabelNode-recalculatePosition] Node positions:', {
    leftmostX,
    leftmostNodeId: leftmostNode.id,
    gapFromLabelRight,
    labelRightEdge,
    actualWidth,
    labelLeftEdge: labelX,
    currentGapFromLabelRight: leftmostX - labelRightEdge,
    targetGap: gapFromLabelRight,
  })

  // Calculate center Y of bridge line (average of all node centers)
  // Use Vue Flow's measured dimensions if available
  interface NodeWithDimensions {
    measured?: { width?: number; height?: number }
    dimensions?: { width?: number; height?: number }
  }

  // Helper to get node dimensions (same pattern as BridgeOverlay)
  const getNodeDimensions = (node: (typeof bridgeNodes)[0] & NodeWithDimensions) => {
    const height = node.dimensions?.height ?? node.measured?.height ?? BRANCH_NODE_HEIGHT
    return { height }
  }

  const allCenters = bridgeNodes.flatMap((node) => {
    const dims = getNodeDimensions(node as (typeof bridgeNodes)[0] & NodeWithDimensions)
    return [node.position.y + dims.height / 2]
  })
  const centerY =
    allCenters.length > 0
      ? allCenters.reduce((a, b) => a + b, 0) / allCenters.length
      : labelNode.position.y + actualHeight / 2 // Fallback to current position

  // Recalculate Y position to center label vertically with bridge line
  const newLabelY = centerY - actualHeight / 2

  // Check if label overlaps with nodes (accounting for gap)
  // Gap is measured from label's right edge to node's left edge
  // Always use maxWidth for calculation to account for worst-case scenario (wrapped text)
  let adjustedX = labelX
  let needsXUpdate = false

  // Maintain gap from label's right edge to horizontal bridge line start (leftmost node's left edge)
  // The horizontal bridge line starts at the leftmost node position (minX)
  // Target: label right edge + gapFromLabelRight = horizontal line start (leftmost node left edge)
  // So: label right edge = leftmost node left edge - gapFromLabelRight
  // Therefore: label left edge = leftmost node left edge - gapFromLabelRight - actualWidth
  const currentGapFromLabelRight = leftmostX - labelRightEdge
  const targetLabelRightEdge = leftmostX - gapFromLabelRight
  const targetLabelX = targetLabelRightEdge - actualWidth

  // Only adjust if the gap is significantly different from target (more than 1px difference)
  if (Math.abs(currentGapFromLabelRight - gapFromLabelRight) > 1) {
    // Calculate new position: move label so its right edge is gapFromLabelRight pixels from node's left edge
    adjustedX = targetLabelX
    // Allow label to go slightly negative if needed, but prefer to keep it at DEFAULT_PADDING minimum
    const minX = -50 // Allow going slightly negative (up to 50px off-canvas)
    adjustedX = Math.max(adjustedX, minX)
    needsXUpdate = Math.abs(adjustedX - labelX) > 1

    console.log('[LabelNode-recalculatePosition] Adjusting to maintain gap:', {
      originalX: labelX,
      originalGap: currentGapFromLabelRight,
      targetGap: gapFromLabelRight,
      targetLabelX,
      adjustedX,
      needsXUpdate,
      reason:
        'Gap from label right edge to horizontal line start (leftmost node left edge) should be 10px',
    })
  } else {
    console.log('[LabelNode-recalculatePosition] Gap is correct, keeping original position:', {
      labelX,
      labelRightEdge,
      leftmostX,
      currentGapFromLabelRight,
      targetGap: gapFromLabelRight,
    })
  }

  // Check if Y position needs update (when height changes due to wrapping)
  const needsYUpdate = Math.abs(newLabelY - labelNode.position.y) > 1

  console.log('[LabelNode-recalculatePosition] Final decision:', {
    adjustedX,
    newLabelY,
    needsXUpdate,
    needsYUpdate,
    willUpdate: updateNode !== undefined && (needsXUpdate || needsYUpdate),
  })

  // Update node position if needed
  if (updateNode && (needsXUpdate || needsYUpdate)) {
    console.log('[LabelNode-recalculatePosition] Updating position:', {
      from: { x: labelNode.position.x, y: labelNode.position.y },
      to: { x: adjustedX, y: newLabelY },
    })
    updateNode(props.id, (node) => ({
      ...node,
      position: { x: adjustedX, y: newLabelY },
    }))
    // Also update in diagram store
    diagramStore.updateNodePosition(props.id, { x: adjustedX, y: newLabelY }, false)
  }
}

// Watch for text changes and recalculate position
watch(
  () => props.data.label,
  () => {
    if (isBridgeDimension.value) {
      nextTick(() => {
        // Wait a bit for DOM to update after text change
        setTimeout(() => {
          recalculatePosition()
        }, 100)
      })
    }
  }
)

// Also listen to text_updated event in case text is updated externally
const unsubTextUpdated = eventBus.on(
  'node:text_updated',
  (payload: { nodeId: string; text: string }) => {
    if (isBridgeDimension.value && payload.nodeId === props.id) {
      nextTick(() => {
        setTimeout(() => {
          recalculatePosition()
        }, 150)
      })
    }
  }
)

// Watch for node position changes (in case nodes move)
watch(
  () => getNodes.value,
  () => {
    if (isBridgeDimension.value) {
      nextTick(() => {
        setTimeout(() => {
          recalculatePosition()
        }, 100)
      })
    }
  },
  { deep: true }
)

// Recalculate on mount and set up ResizeObserver
onMounted(() => {
  if (isBridgeDimension.value && labelRef.value) {
    // Initial recalculation after DOM is ready
    nextTick(() => {
      setTimeout(() => {
        recalculatePosition()
      }, 300)
    })

    // Set up ResizeObserver to detect when label size changes (e.g., text wraps)
    resizeObserver = new ResizeObserver(() => {
      // Debounce recalculation to avoid too many updates
      setTimeout(() => {
        recalculatePosition()
      }, 100)
    })
    resizeObserver.observe(labelRef.value)
  }
})

onUnmounted(() => {
  unsubTextUpdated()
  if (resizeObserver && labelRef.value) {
    resizeObserver.unobserve(labelRef.value)
    resizeObserver.disconnect()
    resizeObserver = null
  }
})

const nodeStyle = computed((): CSSProperties => {
  // For bridge map dimension labels, use different styling (no italic, bold, dark blue)
  const isBridgeDimension = props.data.diagramType === 'bridge_map' && props.data.isDimensionLabel

  return {
    color: isPlaceholder.value ? '#1976d2' : isBridgeDimension ? '#1976d2' : '#1976d2',
    opacity: isPlaceholder.value ? 0.4 : isBridgeDimension ? 1 : 0.8,
    fontFamily: props.data.style?.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${props.data.style?.fontSize || (isBridgeDimension ? 14 : 14)}px`,
    fontStyle: props.data.style?.fontStyle || (isBridgeDimension ? 'normal' : 'italic'),
    fontWeight: props.data.style?.fontWeight || (isBridgeDimension ? 'bold' : 'normal'),
    textDecoration: props.data.style?.textDecoration || 'none',
    textAlign: (isBridgeDimension ? 'right' : 'center') as
      | 'left'
      | 'right'
      | 'center'
      | 'justify'
      | 'start'
      | 'end',
    padding: isBridgeDimension ? '4px 8px' : '4px 8px',
    whiteSpace: isBridgeDimension ? 'normal' : 'nowrap', // Allow natural wrapping for bridge maps
    overflowWrap: (isBridgeDimension ? 'break-word' : 'normal') as
      | 'normal'
      | 'break-word'
      | 'anywhere',
  }
})

// For bridge maps, return two-line format
const bridgeMapDisplay = computed(() => {
  if (props.data.diagramType !== 'bridge_map' || !props.data.isDimensionLabel) {
    return null
  }

  const labelText = t('diagram.labelNode.analogyRelationship')

  // Wrap dimension value in brackets []
  // Strip existing brackets if present to avoid double brackets
  let rawValue = props.data.label?.trim() || ''
  if (rawValue.startsWith('[') && rawValue.endsWith(']')) {
    rawValue = rawValue.slice(1, -1) // Remove existing brackets
  }
  const valueText = rawValue
    ? `[${rawValue}]` // Add brackets around actual value
    : t('diagram.labelNode.clickToSet')

  return {
    label: labelText,
    value: valueText,
    isPlaceholder: !rawValue,
  }
})

function labeledDimensionPrefix(braceMap: boolean, dimensionValue: string): string {
  const hasChinese = /[\u4e00-\u9fa5]/.test(dimensionValue)
  if (hasChinese) {
    return braceMap
      ? t('diagram.dimension.decompositionZh')
      : t('diagram.dimension.classificationZh')
  }
  if (uiStore.language === 'az') {
    return braceMap
      ? t('diagram.dimension.decompositionAz')
      : t('diagram.dimension.classificationAz')
  }
  return braceMap ? t('diagram.dimension.decompositionEn') : t('diagram.dimension.classificationEn')
}

const displayText = computed(() => {
  // For bridge maps, return single string (will be handled separately in template)
  if (props.data.diagramType === 'bridge_map' && props.data.isDimensionLabel) {
    return props.data.label || ''
  }

  const braceMap = props.data.diagramType === 'brace_map'

  if (props.data.label) {
    const dimensionValue =
      braceMap && uiStore.language === 'zh'
        ? translateDimension(props.data.label, true)
        : props.data.label
    const prefix = labeledDimensionPrefix(braceMap, dimensionValue)
    return t('diagram.labelNode.placeholderBracket', {
      prefix,
      hint: dimensionValue,
    })
  }

  const placeholderPrefix = braceMap
    ? t('diagram.labelNode.emptyPrefixBrace')
    : t('diagram.labelNode.emptyPrefixTree')
  return t('diagram.labelNode.placeholderBracket', {
    prefix: placeholderPrefix,
    hint: t('diagram.labelNode.clickToFillHint'),
  })
})

// Inline editing state
const isEditing = ref(false)

function handleTextSave(newText: string) {
  isEditing.value = false
  eventBus.emit('node:text_updated', {
    nodeId: props.id,
    text: newText,
  })
  // Recalculate position after text update to prevent overlap
  if (isBridgeDimension.value) {
    nextTick(() => {
      setTimeout(() => {
        recalculatePosition()
      }, 100)
    })
  }
}

function handleEditCancel() {
  isEditing.value = false
}
</script>

<template>
  <div
    ref="labelRef"
    class="label-node flex cursor-pointer"
    :class="{
      'items-center justify-center select-none': !isBridgeDimension,
      'flex-col items-end justify-center': isBridgeDimension,
    }"
    :style="nodeStyle"
    :data-bridge-dimension="isBridgeDimension ? '' : undefined"
  >
    <!-- Bridge map: two-line format -->
    <template v-if="isBridgeDimension && bridgeMapDisplay">
      <div
        class="label-line text-right select-none"
        style="line-height: 1.2; user-select: none"
      >
        {{ bridgeMapDisplay.label }}
      </div>
      <div
        class="value-line text-right"
        style="line-height: 1.2; margin-top: 2px"
      >
        <InlineEditableText
          :text="bridgeMapDisplay.value"
          :node-id="id"
          :is-editing="isEditing"
          max-width="180px"
          text-align="right"
          :text-decoration="data.style?.textDecoration || 'none'"
          :text-class="bridgeMapDisplay.isPlaceholder ? 'opacity-60' : ''"
          @save="handleTextSave"
          @cancel="handleEditCancel"
          @edit-start="isEditing = true"
        />
      </div>
    </template>

    <!-- Other diagram types: single line -->
    <template v-else>
      <InlineEditableText
        :text="displayText"
        :node-id="id"
        :is-editing="isEditing"
        max-width="200px"
        text-align="center"
        :text-decoration="data.style?.textDecoration || 'none'"
        text-class="whitespace-nowrap"
        @save="handleTextSave"
        @cancel="handleEditCancel"
        @edit-start="isEditing = true"
      />
    </template>
  </div>
</template>

<style scoped>
.label-node {
  min-width: 100px;
  min-height: 24px;
  transition: opacity 0.2s ease;
}

/* Bridge map dimension labels: adaptive width and wrapping */
.label-node[data-bridge-dimension] {
  max-width: 180px;
  /* When wrapping is needed, text will wrap and align left */
  /* When no overlap, text stays right-aligned */
}

.label-node:hover {
  opacity: 1 !important;
}
</style>
