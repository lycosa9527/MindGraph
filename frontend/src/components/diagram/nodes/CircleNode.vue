<script setup lang="ts">
/**
 * CircleNode - Perfect circular node for Circle Maps
 * Used for both topic and context nodes in circle maps
 * Always renders as a perfect circle regardless of content
 * Supports inline text editing on double-click
 * Adapts size based on text length
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import { useDiagramStore } from '@/stores'
import { calculateAdaptiveCircleSize } from '@/stores/specLoader/utils'
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

const diagramStore = useDiagramStore()

// Get the circle size from data or calculate adaptively based on text length
// Both topic and context nodes use adaptive sizing based on text length
const circleSize = computed(() => {
  // If size is explicitly set in style, use it
  if (props.data.style?.size) {
    return props.data.style.size
  }
  
  // Calculate adaptive size based on text length for both topic and context nodes
  const text = props.data.label || ''
  return calculateAdaptiveCircleSize(text, isTopicNode.value)
})

// Watch for text changes and update node size in store (only for topic nodes)
watch(
  () => props.data.label,
  (newText) => {
    if (diagramStore.type === 'circle_map' && isTopicNode.value) {
      const adaptiveSize = calculateAdaptiveCircleSize(newText || '', true)
      // Update the node style in the store to persist the adaptive size
      nextTick(() => {
        diagramStore.saveNodeStyle(props.id, { size: adaptiveSize })
      })
    }
  }
)

// Listen for text_updated event to recalculate size (for both topic and context nodes)
function handleTextUpdated(payload: { nodeId: string; text: string }) {
  if (payload.nodeId === props.id && diagramStore.type === 'circle_map') {
    const adaptiveSize = calculateAdaptiveCircleSize(payload.text, isTopicNode.value)
    nextTick(() => {
      diagramStore.saveNodeStyle(payload.nodeId, { size: adaptiveSize })
    })
  }
}

onMounted(() => {
  eventBus.on('node:text_updated', handleTextUpdated)
})

onUnmounted(() => {
  eventBus.off('node:text_updated', handleTextUpdated)
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
  // Update size adaptively based on new text (only for topic nodes)
  if (diagramStore.type === 'circle_map' && isTopicNode.value) {
    const adaptiveSize = calculateAdaptiveCircleSize(newText, true)
    diagramStore.saveNodeStyle(props.id, { size: adaptiveSize })
  }
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
