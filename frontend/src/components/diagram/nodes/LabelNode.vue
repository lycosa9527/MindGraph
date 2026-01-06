<script setup lang="ts">
/**
 * LabelNode - Text label node for dimension labels and annotations
 * Used for displaying classification dimensions in Tree Maps and Brace Maps
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'

import { eventBus } from '@/composables/useEventBus'
import type { MindGraphNodeProps } from '@/types'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const isPlaceholder = computed(() => props.data.isPlaceholder || !props.data.label)

const nodeStyle = computed(() => ({
  color: isPlaceholder.value ? '#1976d2' : '#1976d2',
  opacity: isPlaceholder.value ? 0.4 : 0.8,
  fontSize: `${props.data.style?.fontSize || 14}px`,
  fontStyle: 'italic',
  fontWeight: props.data.style?.fontWeight || 'normal',
}))

const displayText = computed(() => {
  if (props.data.label) {
    // Determine language from content
    const hasChinese = /[\u4e00-\u9fa5]/.test(props.data.label)
    const prefix = hasChinese ? '分类维度' : 'Classification by'
    return `[${prefix}: ${props.data.label}]`
  }
  // Placeholder text
  const hasChinese = /[\u4e00-\u9fa5]/.test(String(props.data.diagramType || ''))
  return hasChinese ? '[分类维度: 点击填写...]' : '[Classification by: click to specify...]'
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
    class="label-node flex items-center justify-center px-2 py-1 cursor-pointer select-none"
    :style="nodeStyle"
  >
    <InlineEditableText
      :text="displayText"
      :node-id="id"
      :is-editing="isEditing"
      max-width="200px"
      text-align="center"
      text-class="whitespace-nowrap"
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />
  </div>
</template>

<style scoped>
.label-node {
  min-width: 100px;
  min-height: 24px;
  transition: opacity 0.2s ease;
  font-family: 'Inter', 'Segoe UI', sans-serif;
}

.label-node:hover {
  opacity: 1 !important;
}
</style>
