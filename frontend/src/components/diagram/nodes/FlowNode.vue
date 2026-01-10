<script setup lang="ts">
/**
 * FlowNode - Step node for flow maps
 * Represents sequential steps in a process flow
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import type { MindGraphNodeProps } from '@/types'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

// Get theme defaults matching old StyleManager
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const defaultStyle = computed(() => getNodeStyle('step'))

const nodeStyle = computed(() => ({
  backgroundColor:
    props.data.style?.backgroundColor || defaultStyle.value.backgroundColor || '#ffffff',
  borderColor: props.data.style?.borderColor || defaultStyle.value.borderColor || '#409eff',
  color: props.data.style?.textColor || defaultStyle.value.textColor || '#303133',
  fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 13}px`,
  fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'normal',
  borderWidth: `${props.data.style?.borderWidth || defaultStyle.value.borderWidth || 2}px`,
  borderRadius: `${props.data.style?.borderRadius || 6}px`,
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
    class="flow-node flex items-center justify-center px-5 py-3 border-solid cursor-grab select-none"
    :style="nodeStyle"
  >
    <InlineEditableText
      :text="data.label || ''"
      :node-id="id"
      :is-editing="isEditing"
      max-width="120px"
      text-align="center"
      truncate
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />

    <!-- Connection handles for vertical flow (top-to-bottom between steps) -->
    <Handle
      id="top"
      type="target"
      :position="Position.Top"
      class="!bg-blue-500"
    />
    <Handle
      id="bottom"
      type="source"
      :position="Position.Bottom"
      class="!bg-blue-500"
    />
    <!-- Connection handles for horizontal flow (left-to-right between steps) -->
    <Handle
      id="left"
      type="target"
      :position="Position.Left"
      class="!bg-blue-500"
    />
    <Handle
      id="right"
      type="source"
      :position="Position.Right"
      class="!bg-blue-500"
    />
    <!-- Secondary source handle on right side for substep connections (vertical mode) -->
    <Handle
      id="substep-source"
      type="source"
      :position="Position.Right"
      class="!bg-blue-400"
    />
  </div>
</template>

<style scoped>
.flow-node {
  width: 140px;
  height: 50px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition:
    box-shadow 0.2s ease,
    transform 0.15s ease;
}

.flow-node:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-1px);
}

.flow-node:active {
  cursor: grabbing;
  transform: translateY(0);
}
</style>
