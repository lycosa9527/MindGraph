<script setup lang="ts">
/**
 * CircleNode - Perfect circular node for Circle Maps
 * Used for both topic and context nodes in circle maps
 * Always renders as a perfect circle regardless of content
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'

import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import type { MindGraphNodeProps } from '@/types'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

// Get theme defaults
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

// Determine if this is a topic or context node
const isTopicNode = computed(() => props.data.nodeType === 'topic')

// Use 'context' for circle map context nodes (not 'bubble')
const defaultStyle = computed(() => getNodeStyle(isTopicNode.value ? 'topic' : 'context'))

// Get the circle size from data or calculate based on node type
const circleSize = computed(() => {
  // Topic nodes are larger (diameter ~120px)
  // Context nodes are smaller (diameter ~70px)
  const size = props.data.style?.size || (isTopicNode.value ? 120 : 70)
  return size
})

// Circle Map colors matching old JS bubble-map-renderer.js THEME
// Topic: fill #1976d2 (blue), text #fff, stroke #0d47a1, strokeWidth 3
// Context: fill #e3f2fd (light blue), text #333, stroke #1976d2, strokeWidth 2
const nodeStyle = computed(() => ({
  width: `${circleSize.value}px`,
  height: `${circleSize.value}px`,
  backgroundColor:
    props.data.style?.backgroundColor ||
    defaultStyle.value.backgroundColor ||
    (isTopicNode.value ? '#1976d2' : '#e3f2fd'),
  borderColor:
    props.data.style?.borderColor ||
    defaultStyle.value.borderColor ||
    (isTopicNode.value ? '#0d47a1' : '#1976d2'),
  color:
    props.data.style?.textColor ||
    defaultStyle.value.textColor ||
    (isTopicNode.value ? '#ffffff' : '#333333'),
  fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || (isTopicNode.value ? 20 : 14)}px`,
  fontWeight:
    props.data.style?.fontWeight ||
    defaultStyle.value.fontWeight ||
    (isTopicNode.value ? 'bold' : 'normal'),
  borderWidth: `${props.data.style?.borderWidth || defaultStyle.value.borderWidth || (isTopicNode.value ? 3 : 2)}px`,
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
    class="circle-node flex items-center justify-center rounded-full border-solid select-none"
    :class="[
      isTopicNode ? 'cursor-default' : 'cursor-grab',
      isTopicNode ? 'topic-circle' : 'context-circle',
    ]"
    :style="nodeStyle"
  >
    <InlineEditableText
      :text="data.label || ''"
      :node-id="id"
      :is-editing="isEditing"
      :max-width="`${circleSize - 16}px`"
      text-align="center"
      :text-class="isTopicNode ? 'px-3 py-2' : 'px-2 py-1'"
      @save="handleTextSave"
      @cancel="handleEditCancel"
      @edit-start="isEditing = true"
    />
  </div>
</template>

<style scoped>
.circle-node {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;
  /* Ensure perfect circle - override any flex sizing */
  flex-shrink: 0;
  aspect-ratio: 1;
}

.context-circle:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: scale(1.02);
}

.context-circle:active {
  cursor: grabbing;
}

.topic-circle {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 10;
}

.topic-circle:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}
</style>
