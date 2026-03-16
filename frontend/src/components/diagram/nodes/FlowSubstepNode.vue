<script setup lang="ts">
/**
 * FlowSubstepNode - Substep node for flow maps
 * Represents detailed sub-steps attached to main flow steps
 * Flow map: pill shape, mindmapColors (same as parent step), fixed size
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { getMindmapBranchColor } from '@/config/mindmapColors'
import { eventBus } from '@/composables/useEventBus'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import type { MindGraphNodeProps } from '@/types'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const isFlowMap = computed(() => props.data.diagramType === 'flow_map')
const groupColor = computed(() => {
  const idx = props.data.groupIndex as number | undefined
  return idx !== undefined && isFlowMap.value ? getMindmapBranchColor(idx) : null
})

const nodeStyle = computed(() => {
  const color = groupColor.value
  const borderColor =
    props.data.style?.borderColor ||
    color?.border ||
    '#1976d2'
  const borderWidth = props.data.style?.borderWidth || 1
  const borderStyle = props.data.style?.borderStyle || 'solid'
  const backgroundColor =
    props.data.style?.backgroundColor ||
    color?.fill ||
    '#e3f2fd'
  const baseStyle = {
    backgroundColor,
    color: props.data.style?.textColor || '#333333',
    fontSize: `${props.data.style?.fontSize || 12}px`,
    fontWeight: props.data.style?.fontWeight || 'normal',
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
    borderRadius: isFlowMap.value
      ? '9999px'
      : `${props.data.style?.borderRadius || 4}px`,
  }
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
</script>

<template>
  <div
    class="flow-substep-node flex items-center justify-center px-3 py-2 border-solid cursor-grab select-none"
    :class="{ 'pill-shape': isFlowMap }"
    :style="nodeStyle"
  >
    <InlineEditableText
      :text="data.label || ''"
      :readonly="data.hidden === true"
      :node-id="id"
      :is-editing="isEditing"
      :max-width="isFlowMap ? 'none' : '94px'"
      text-align="center"
      :text-decoration="data.style?.textDecoration || 'none'"
      :truncate="!isFlowMap"
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
  width: 100px;
  height: 50px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  transition:
    box-shadow 0.2s ease,
    transform 0.15s ease;
}

.flow-substep-node.pill-shape {
  width: 120px;
  height: 48px;
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
