<script setup lang="ts">
/**
 * BubbleNode - Circular attribute node for bubble maps
 * Represents attributes/qualities surrounding a central topic
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'

import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import type { MindGraphNodeProps } from '@/types'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

// Get theme defaults matching old StyleManager
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const defaultStyle = computed(() => getNodeStyle('bubble'))

const nodeStyle = computed(() => ({
  backgroundColor:
    props.data.style?.backgroundColor || defaultStyle.value.backgroundColor || '#e3f2fd',
  borderColor: props.data.style?.borderColor || defaultStyle.value.borderColor || '#000000',
  color: props.data.style?.textColor || defaultStyle.value.textColor || '#333333',
  fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 14}px`,
  fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'normal',
  fontStyle: props.data.style?.fontStyle || 'normal',
  textDecoration: props.data.style?.textDecoration || 'none',
  borderWidth: `${props.data.style?.borderWidth || defaultStyle.value.borderWidth || 2}px`,
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
    class="bubble-node flex items-center justify-center rounded-full border-solid cursor-grab select-none"
    :style="nodeStyle"
  >
    <InlineEditableText
      :text="data.label || ''"
      :node-id="id"
      :is-editing="isEditing"
      max-width="100px"
      text-align="center"
      text-class="px-3 py-2"
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />
  </div>
</template>

<style scoped>
.bubble-node {
  min-width: 90px;
  min-height: 50px;
  padding: 8px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.bubble-node:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: scale(1.02);
}

.bubble-node:active {
  cursor: grabbing;
}
</style>
