<script setup lang="ts">
/**
 * TopicNode - Central topic node for diagrams (non-draggable)
 * Used as the main/central node in bubble maps, mind maps, etc.
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

const defaultStyle = computed(() => getNodeStyle('topic'))

// Tree map and brace map use pill shape (fully rounded ends), others use default circle
const isPillShape = computed(
  () => props.data.diagramType === 'tree_map' || props.data.diagramType === 'brace_map'
)

// Specific diagram type checks for handle positioning
const isTreeMap = computed(() => props.data.diagramType === 'tree_map')
const isBraceMap = computed(() => props.data.diagramType === 'brace_map')

const nodeStyle = computed(() => ({
  backgroundColor:
    props.data.style?.backgroundColor || defaultStyle.value.backgroundColor || '#1976d2',
  borderColor: props.data.style?.borderColor || defaultStyle.value.borderColor || '#0d47a1',
  color: props.data.style?.textColor || defaultStyle.value.textColor || '#ffffff',
  fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 18}px`,
  fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'bold',
  borderWidth: `${props.data.style?.borderWidth || defaultStyle.value.borderWidth || 3}px`,
  // Pill shape for tree map (9999px creates fully rounded ends), circle for others
  borderRadius: isPillShape.value ? '9999px' : `${props.data.style?.borderRadius || 50}%`,
}))

// Inline editing state
const isEditing = ref(false)

function handleTextSave(newText: string) {
  isEditing.value = false
  // Emit event to update the node text in the store
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
    class="topic-node flex items-center justify-center px-6 py-4 border-solid cursor-default select-none"
    :class="{ 'pill-shape': isPillShape }"
    :style="nodeStyle"
  >
    <InlineEditableText
      :text="data.label || ''"
      :node-id="id"
      :is-editing="isEditing"
      max-width="200px"
      text-align="center"
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />

    <!-- Connection handles for horizontal layouts (mind maps, bubble maps, etc.) -->
    <Handle
      v-if="!isPillShape"
      type="source"
      :position="Position.Right"
      class="!bg-blue-500"
    />
    <Handle
      v-if="!isPillShape"
      type="source"
      :position="Position.Left"
      class="!bg-blue-500"
    />
    <Handle
      v-if="!isPillShape"
      type="source"
      :position="Position.Top"
      class="!bg-blue-500"
    />
    <Handle
      v-if="!isPillShape"
      type="source"
      :position="Position.Bottom"
      class="!bg-blue-500"
    />

    <!-- Connection handle for tree maps (vertical layout - bottom only) -->
    <Handle
      v-if="isTreeMap"
      type="source"
      :position="Position.Bottom"
      class="!bg-blue-500"
    />

    <!-- Connection handle for brace maps (horizontal layout - right only) -->
    <Handle
      v-if="isBraceMap"
      type="source"
      :position="Position.Right"
      class="!bg-blue-500"
    />
  </div>
</template>

<style scoped>
.topic-node {
  min-width: 120px;
  min-height: 48px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: box-shadow 0.2s ease;
}

.topic-node:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

/* Tree map pill shape adjustments */
.topic-node.pill-shape {
  min-height: 40px;
  padding-left: 24px;
  padding-right: 24px;
}
</style>
