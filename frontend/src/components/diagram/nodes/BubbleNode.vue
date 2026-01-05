<script setup lang="ts">
/**
 * BubbleNode - Circular attribute node for bubble maps
 * Represents attributes/qualities surrounding a central topic
 */
import { computed } from 'vue'

import { Handle, Position } from '@vue-flow/core'

import { useTheme } from '@/composables/useTheme'
import type { MindGraphNodeProps } from '@/types'

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
  borderWidth: `${props.data.style?.borderWidth || defaultStyle.value.borderWidth || 2}px`,
}))
</script>

<template>
  <div
    class="bubble-node flex items-center justify-center rounded-full border-solid cursor-grab select-none"
    :style="nodeStyle"
  >
    <span class="text-center whitespace-pre-wrap px-3 py-2 max-w-[100px]">
      {{ data.label }}
    </span>

    <!-- Connection handle (center) -->
    <Handle
      type="target"
      :position="Position.Left"
      class="!bg-slate-400"
    />
  </div>
</template>

<style scoped>
.bubble-node {
  min-width: 70px;
  min-height: 70px;
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
