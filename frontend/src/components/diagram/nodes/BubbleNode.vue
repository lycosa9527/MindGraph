<script setup lang="ts">
/**
 * BubbleNode - Circular attribute node for bubble maps
 * Represents attributes/qualities surrounding a central topic
 * Supports inline text editing on double-click
 */
import { computed, ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useTheme } from '@/composables/core/useTheme'
import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { computeScriptAwareMaxWidth } from '@/stores/specLoader/textMeasurementFallback'
import type { MindGraphNodeProps } from '@/types'
import { getBorderStyleProps } from '@/utils/borderStyleUtils'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

import InlineEditableText from './InlineEditableText.vue'

const props = defineProps<MindGraphNodeProps>()

const bubbleNodeRef = ref<HTMLElement | null>(null)
useNodeDimensions(bubbleNodeRef, props.id)

// Get theme defaults matching old StyleManager
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const defaultStyle = computed(() => getNodeStyle('bubble'))

const BUBBLE_BASE_MAX_WIDTH = 140
const bubbleMaxWidth = computed(() => {
  const label = (props.data.label as string) || ''
  return `${computeScriptAwareMaxWidth(label, BUBBLE_BASE_MAX_WIDTH)}px`
})

const nodeStyle = computed(() => {
  const borderColor = props.data.style?.borderColor || defaultStyle.value.borderColor || '#000000'
  const borderWidth = props.data.style?.borderWidth || defaultStyle.value.borderWidth || 2
  const borderStyle = props.data.style?.borderStyle || 'solid'
  const backgroundColor =
    props.data.style?.backgroundColor || defaultStyle.value.backgroundColor || '#e3f2fd'
  return {
    backgroundColor,
    color: props.data.style?.textColor || defaultStyle.value.textColor || '#333333',
    fontFamily: props.data.style?.fontFamily || DIAGRAM_NODE_FONT_STACK,
    fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 14}px`,
    fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'normal',
    fontStyle: props.data.style?.fontStyle || 'normal',
    textDecoration: props.data.style?.textDecoration || 'none',
    ...getBorderStyleProps(borderColor, borderWidth, borderStyle, {
      backgroundColor,
    }),
  }
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
    ref="bubbleNodeRef"
    class="bubble-node flex items-center justify-center rounded-full border-solid cursor-grab select-none"
    :style="nodeStyle"
  >
    <InlineEditableText
      :text="data.label || ''"
      :readonly="data.hidden === true"
      :node-id="id"
      :is-editing="isEditing"
      :max-width="bubbleMaxWidth"
      :text-align="data.style?.textAlign || 'center'"
      :text-decoration="data.style?.textDecoration || 'none'"
      text-class="px-3 py-2"
      render-markdown
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
