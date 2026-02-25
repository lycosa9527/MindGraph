<script setup lang="ts">
/**
 * FlowSubstepNode - Substep node for flow maps
 * Represents detailed sub-steps attached to main flow steps
 * Uses lighter blue styling matching old JS renderer theme
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { eventBus } from '@/composables/useEventBus'
import type { MindGraphNodeProps } from '@/types'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

// Substep theme colors matching old JS flow-renderer.js
// substepFill: '#e3f2fd', substepText: '#333333', substepStroke: '#1976d2'
const nodeStyle = computed(() => ({
  backgroundColor: props.data.style?.backgroundColor || '#e3f2fd',
  borderColor: props.data.style?.borderColor || '#1976d2',
  color: props.data.style?.textColor || '#333333',
  fontSize: `${props.data.style?.fontSize || 12}px`,
  fontWeight: props.data.style?.fontWeight || 'normal',
  fontStyle: props.data.style?.fontStyle || 'normal',
  textDecoration: props.data.style?.textDecoration || 'none',
  borderWidth: `${props.data.style?.borderWidth || 1}px`,
  borderRadius: `${props.data.style?.borderRadius || 4}px`,
}))

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
    :style="nodeStyle"
  >
    <InlineEditableText
      :text="data.label || ''"
      :node-id="id"
      :is-editing="isEditing"
      max-width="94px"
      text-align="center"
      truncate
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />

    <!-- Connection handle on left side for L-shaped connector from parent step -->
    <Handle
      type="target"
      :position="Position.Left"
      class="!bg-blue-400"
    />
    <!-- Additional handle on top for alternative connection routing -->
    <Handle
      id="top-target"
      type="target"
      :position="Position.Top"
      class="!bg-blue-400"
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
</style>
