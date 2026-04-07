<script setup lang="ts">
/**
 * FlowSubstepNode - Substep node for flow maps
 * Represents detailed sub-steps attached to main flow steps
 * Flow map: pill shape, mindmapColors (same as parent step), fixed size
 * Supports inline text editing on double-click
 */
import { computed, inject, ref } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { eventBus } from '@/composables/core/useEventBus'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import { measureTextWidth } from '@/stores/specLoader/textMeasurement'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const flowSubstepNodeRef = ref<HTMLElement | null>(null)
useNodeDimensions(flowSubstepNodeRef, props.id)

const isFlowMap = computed(() => props.data.diagramType === 'flow_map')
const groupColor = computed(() => {
  const idx = props.data.groupIndex as number | undefined
  return idx !== undefined && isFlowMap.value ? getMindmapBranchColor(idx) : null
})

const nodeStyle = computed(() => {
  const color = groupColor.value
  const borderColor = props.data.style?.borderColor || color?.border || '#1976d2'
  const borderWidth = props.data.style?.borderWidth || 1
  const borderStyle = props.data.style?.borderStyle || 'solid'
  const backgroundColor = props.data.style?.backgroundColor || color?.fill || '#e3f2fd'
  const baseStyle = {
    backgroundColor,
    color: props.data.style?.textColor || '#333333',
    fontFamily: props.data.style?.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${props.data.style?.fontSize || 12}px`,
    fontWeight: props.data.style?.fontWeight || 'normal',
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
    borderRadius: isFlowMap.value ? '9999px' : `${props.data.style?.borderRadius || 4}px`,
  }
  if (isFlowMap.value) {
    return {
      ...baseStyle,
      width: 'max-content',
      minWidth: '120px',
      minHeight: '48px',
      maxWidth: '230px',
    }
  }
  return baseStyle
})

const SUBSTEP_MAX_TEXT_WIDTH = 180
const BALANCE_PADDING = 5

const substepMaxWidth = computed(() => {
  if (!isFlowMap.value) return '140px'

  const label = ((props.data.label as string) || '').trim()
  if (!label) return `${SUBSTEP_MAX_TEXT_WIDTH}px`

  const fontSize = parseFloat(nodeStyle.value.fontSize as string) || 12
  const fontWeight = String(nodeStyle.value.fontWeight || 'normal')
  const textWidth = measureTextWidth(label, fontSize, { fontWeight })

  if (textWidth <= SUBSTEP_MAX_TEXT_WIDTH) return `${SUBSTEP_MAX_TEXT_WIDTH}px`

  const numLines = Math.ceil(textWidth / SUBSTEP_MAX_TEXT_WIDTH)
  const balancedWidth = Math.ceil(textWidth / numLines) + BALANCE_PADDING
  return `${Math.min(balancedWidth, SUBSTEP_MAX_TEXT_WIDTH)}px`
})

// Inline editing state
const isEditing = ref(false)

function handleTextSave(newText: string) {
  isEditing.value = false
  eventBus.emit('node:text_updated', {
    nodeId: props.id,
    text: newText,
  })
}

function handleEditCancel() {
  isEditing.value = false
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

const supportsBranchMove = computed(() => isFlowMap.value && props.id?.startsWith('flow-substep-'))

function handleBranchMovePointerDown(event: MouseEvent): void {
  if (supportsBranchMove.value) {
    branchMove.onBranchMovePointerDown(props.id, isEditing.value, event.clientX, event.clientY)
  }
}

function handleBranchMoveTouchStart(event: TouchEvent): void {
  if (!supportsBranchMove.value || event.touches.length !== 1) return
  const touch = event.touches[0]
  const consumed = branchMove.onBranchMovePointerDown(
    props.id,
    isEditing.value,
    touch.clientX,
    touch.clientY,
    true
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
    ref="flowSubstepNodeRef"
    class="flow-substep-node flex items-center justify-center px-3 py-2 border-solid cursor-grab select-none"
    :class="{ 'pill-shape': isFlowMap }"
    :style="nodeStyle"
    @mousedown.capture="handleBranchMovePointerDown"
    @mouseup.capture="handleBranchMovePointerUp"
    @touchstart.capture="handleBranchMoveTouchStart"
  >
    <InlineEditableText
      :text="data.label || ''"
      :readonly="data.hidden === true"
      :node-id="id"
      :is-editing="isEditing"
      :max-width="substepMaxWidth"
      :text-align="data.style?.textAlign || 'center'"
      :text-decoration="data.style?.textDecoration || 'none'"
      :truncate="!isFlowMap"
      :auto-wrap="isFlowMap"
      render-markdown
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />

    <!-- Connection handle on left side for step-to-substep (vertical layout) -->
    <Handle
      id="left"
      type="target"
      :position="Position.Left"
      class="!bg-blue-400"
    />
    <!-- Top handle for substeps below step (vertical layout) -->
    <Handle
      id="top-target"
      type="target"
      :position="Position.Top"
      class="!bg-blue-400"
    />
    <!-- Bottom handle for substeps above step (vertical layout) -->
    <Handle
      id="bottom-target"
      type="target"
      :position="Position.Bottom"
      class="!bg-blue-400"
    />
    <!-- Bottom source handle for main flow: connect from bottom substep to next step -->
    <Handle
      id="bottom-source"
      type="source"
      :position="Position.Bottom"
      class="!bg-blue-400"
    />
    <!-- Center handles for flow map: connect to node center (experiment to eliminate gap) -->
    <Handle
      id="center-target"
      type="target"
      :position="Position.Top"
      class="center-handle !bg-blue-400"
    />
    <Handle
      id="center-source"
      type="source"
      :position="Position.Top"
      class="center-handle !bg-blue-400"
    />
  </div>
</template>

<style scoped>
.flow-substep-node {
  width: max-content;
  min-width: 100px;
  min-height: 50px;
  overflow: visible;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  transition:
    box-shadow 0.2s ease,
    transform 0.15s ease;
}

.flow-substep-node.pill-shape {
  width: 120px;
  min-height: 48px;
  padding-left: 20px;
  padding-right: 20px;
}

.flow-substep-node:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  transform: translateY(-1px);
}

.flow-substep-node:active {
  cursor: grabbing;
  transform: translateY(0);
}

/* Hide handle dots visually while keeping them functional */
.flow-substep-node :deep(.vue-flow__handle) {
  opacity: 0;
  border: none;
  background: transparent;
}

/* Center handle: position at node center */
.flow-substep-node :deep(.center-handle) {
  left: 50% !important;
  top: 50% !important;
  right: auto !important;
  bottom: auto !important;
  transform: translate(-50%, -50%);
}
</style>
