<script setup lang="ts">
/**
 * FlowNode - Step node for flow maps
 * Represents sequential steps in a process flow
 * Supports inline text editing on double-click
 * Uses mindmap branch color palette for multi-flow map causes/effects
 */
import { computed, inject, nextTick, ref } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { X } from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import { useDiagramStore } from '@/stores'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const { t } = useLanguage()

// Get theme defaults matching old StyleManager
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const defaultStyle = computed(() => getNodeStyle('step'))

// Flow map and multi-flow map use pill shape (fully rounded ends)
const isFlowMap = computed(() => props.data.diagramType === 'flow_map')
const isPillShape = computed(
  () => props.data.diagramType === 'multi_flow_map' || props.data.diagramType === 'flow_map'
)
const isMultiFlowMap = computed(() => props.data.diagramType === 'multi_flow_map')
// For multi-flow map: causes connect from right, effects connect to left
const isCause = computed(() => isMultiFlowMap.value && props.id.startsWith('cause-'))
const isEffect = computed(() => isMultiFlowMap.value && props.id.startsWith('effect-'))

// Per-group color from mindmap palette for flow map steps and multi-flow map causes/effects
const groupColor = computed(() => {
  const idx = props.data.groupIndex as number | undefined
  return idx !== undefined && (isFlowMap.value || isMultiFlowMap.value)
    ? getMindmapBranchColor(idx)
    : null
})

const nodeStyle = computed(() => {
  const color = groupColor.value
  const borderColor =
    props.data.style?.borderColor || color?.border || defaultStyle.value.borderColor || '#409eff'
  const borderWidth = props.data.style?.borderWidth || defaultStyle.value.borderWidth || 2
  const borderStyle = props.data.style?.borderStyle || 'solid'
  const backgroundColor =
    props.data.style?.backgroundColor ||
    color?.fill ||
    defaultStyle.value.backgroundColor ||
    '#ffffff'

  const baseStyle = {
    backgroundColor,
    color: props.data.style?.textColor || defaultStyle.value.textColor || '#303133',
    fontFamily: props.data.style?.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 13}px`,
    fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
    // Pill shape for multi-flow map (9999px creates fully rounded ends), default rounded rectangle for others
    borderRadius: isPillShape.value ? '9999px' : `${props.data.style?.borderRadius || 6}px`,
  }

  // Add dynamic width when editing (multi-flow map only; flow_map uses fixed pill size)
  if (isMultiFlowMap.value && dynamicWidth.value !== null) {
    return {
      ...baseStyle,
      width: `${dynamicWidth.value}px`,
      minWidth: `${dynamicWidth.value}px`,
    }
  }

  // Multi-flow map: use layout width so full text displays (not fixed 140px)
  if (isMultiFlowMap.value && layoutWidth.value !== null) {
    return {
      ...baseStyle,
      width: `${layoutWidth.value}px`,
      minWidth: `${layoutWidth.value}px`,
    }
  }

  // Flow map: adaptive width (min 120px) so full text displays
  if (isFlowMap.value) {
    return {
      ...baseStyle,
      width: 'max-content',
      minWidth: '120px',
      height: '48px',
    }
  }

  return baseStyle
})

// Inline editing state
const isEditing = ref(false)

// Hover state for delete button (only for multi-flow map)
const isHovering = ref(false)

// Dynamic width for editing
const dynamicWidth = ref<number | null>(null)

const diagramStore = useDiagramStore()

// Layout width for multi-flow map (from recalculateMultiFlowMapLayout)
// Used when not editing so node displays full text instead of fixed 140px
const layoutWidth = computed(() => {
  if (!isMultiFlowMap.value || dynamicWidth.value !== null) return null
  const node = diagramStore.vueFlowNodes.find((n) => n.id === props.id)
  const style = node?.style as { width?: number; minWidth?: number } | undefined
  const w = style?.width ?? style?.minWidth
  return typeof w === 'number' ? w : null
})

function handleTextSave(newText: string) {
  isEditing.value = false
  const savedWidth = dynamicWidth.value
  dynamicWidth.value = null // Reset width after saving

  // Store the width for visual balance calculation
  if (isMultiFlowMap.value && savedWidth !== null) {
    diagramStore.setNodeWidth(props.id, savedWidth)
  }

  eventBus.emit('node:text_updated', {
    nodeId: props.id,
    text: newText,
  })

  // Trigger layout recalculation for multi-flow map to update visual balance
  if (isMultiFlowMap.value) {
    nextTick(() => {
      eventBus.emit('multi_flow_map:node_width_changed', {
        nodeId: props.id,
        width: savedWidth,
      })
    })
  }
}

function handleEditCancel() {
  isEditing.value = false
  dynamicWidth.value = null // Reset width after canceling
}

function handleWidthChange(width: number) {
  // Update node width dynamically as user types
  // Add padding to account for node padding (px-5 = 20px on each side = 40px total)
  dynamicWidth.value = width + 40
}

function handleDeleteClick(event: MouseEvent) {
  event.stopPropagation()
  if (diagramStore.removeNode(props.id)) {
    diagramStore.pushHistory(t('diagram.history.deleteNode'))
  }
}

const branchMove = inject<{
  onBranchMovePointerDown: (
    nodeId: string,
    isEditing: boolean,
    clientX?: number,
    clientY?: number,
    fromTouch?: boolean
  ) => boolean
  onBranchMovePointerUp: () => void
}>('branchMove', { onBranchMovePointerDown: () => false, onBranchMovePointerUp: () => {} })

const supportsBranchMove = computed(() => {
  if (isFlowMap.value) return props.id?.startsWith('flow-step-')
  if (isMultiFlowMap.value) return isCause.value || isEffect.value
  return false
})

function handleBranchMovePointerDown(event: MouseEvent): void {
  if (supportsBranchMove.value) {
    branchMove.onBranchMovePointerDown(props.id, isEditing.value, event.clientX, event.clientY)
  }
}

function handleBranchMoveTouchStart(event: TouchEvent): void {
  if (!supportsBranchMove.value || event.touches.length !== 1) return
  const touch = event.touches[0]
  const consumed = branchMove.onBranchMovePointerDown(
    props.id, isEditing.value, touch.clientX, touch.clientY, true,
  )
  if (consumed) {
    event.stopPropagation()
    event.preventDefault()
  }
}

function handleBranchMovePointerUp(): void {
  if (supportsBranchMove.value) {
    branchMove.onBranchMovePointerUp()
  }
}
</script>

<template>
  <div
    class="flow-node flex items-center justify-center px-5 py-3 border-solid cursor-grab select-none relative"
    :class="{ 'pill-shape': isPillShape, 'multi-flow-map-node': isMultiFlowMap }"
    :style="nodeStyle"
    @mouseenter="isHovering = true"
    @mouseleave="isHovering = false"
    @mousedown.capture="handleBranchMovePointerDown"
    @mouseup.capture="handleBranchMovePointerUp"
    @touchstart.capture="handleBranchMoveTouchStart"
  >
    <!-- Delete button - positioned using Vue Flow handle positioning system (Top + Right) -->
    <!-- Positioned at top-right corner using same absolute positioning as handles -->
    <button
      v-if="isMultiFlowMap && isHovering"
      class="delete-button"
      :class="{ 'pointer-events-none': isEditing }"
      @click="handleDeleteClick"
      @mousedown.stop
    >
      <X class="w-4 h-4" />
    </button>

    <InlineEditableText
      :text="data.label || ''"
      :readonly="data.hidden === true"
      :node-id="id"
      :is-editing="isEditing"
      :max-width="isPillShape ? 'none' : '200px'"
      text-align="center"
      :text-decoration="data.style?.textDecoration || 'none'"
      :truncate="!isPillShape"
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
      @width-change="handleWidthChange"
    />

    <!-- Connection handles for vertical flow (top-to-bottom between steps) -->
    <!-- Hide for multi-flow map (uses horizontal connections only) -->
    <Handle
      v-if="!isMultiFlowMap"
      id="top"
      type="target"
      :position="Position.Top"
      class="bg-blue-500!"
    />
    <Handle
      v-if="!isMultiFlowMap"
      id="bottom"
      type="source"
      :position="Position.Bottom"
      class="bg-blue-500!"
    />
    <!-- Connection handles for horizontal flow (left-to-right between steps) -->
    <!-- For multi-flow map: causes only have right handle, effects only have left handle -->
    <Handle
      v-if="!isMultiFlowMap || isEffect"
      id="left"
      type="target"
      :position="Position.Left"
      class="bg-blue-500!"
    />
    <Handle
      v-if="!isMultiFlowMap || isCause"
      id="right"
      type="source"
      :position="Position.Right"
      class="bg-blue-500!"
    />
    <!-- Secondary source handle on right side for substep connections (vertical mode) -->
    <!-- Hide for multi-flow map -->
    <Handle
      v-if="!isMultiFlowMap"
      id="substep-source"
      type="source"
      :position="Position.Right"
      class="bg-blue-400!"
    />
    <!-- Center source for flow map step-to-substep (connect to substep center) -->
    <Handle
      v-if="!isMultiFlowMap"
      id="center-source"
      type="source"
      :position="Position.Top"
      class="center-handle bg-blue-400!"
    />
  </div>
</template>

<style scoped>
.flow-node {
  width: 140px;
  min-width: 140px; /* Minimum width */
  height: 50px;
  overflow: visible; /* Changed from hidden to visible so delete button isn't clipped */
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition:
    box-shadow 0.2s ease,
    transform 0.15s ease,
    width 0.2s ease; /* Smooth width transition */
}

.flow-node:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-1px);
}

.flow-node:active {
  cursor: grabbing;
  transform: translateY(0);
}

/* Multi-flow map pill shape adjustments */
.flow-node.pill-shape {
  padding-left: 20px;
  padding-right: 20px;
}

/* Hide handle dots visually while keeping them functional */
.flow-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}

/* Center handle: position at node center */
.flow-node :deep(.center-handle) {
  left: 50% !important;
  top: 50% !important;
  right: auto !important;
  bottom: auto !important;
  transform: translate(-50%, -50%);
}

/* Delete button - positioned using Vue Flow handle positioning system */
/* Vue Flow handles use absolute positioning relative to node container */
/* For top-right: position at top: 0, right: 0, then offset by half button size */
.delete-button {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background-color: #ef4444;
  color: white;
  border: none;
  cursor: pointer;
  opacity: 0.8;
  transition:
    opacity 0.2s ease,
    transform 0.15s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  z-index: 10;
}

.delete-button:hover {
  background-color: #dc2626;
  opacity: 1;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
}

.delete-button:active {
  transform: scale(0.95);
}
</style>
