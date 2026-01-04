<script setup lang="ts">
/**
 * FlowNode - Step node for flow maps
 * Represents sequential steps in a process flow
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

const defaultStyle = computed(() => getNodeStyle('step'))

const nodeStyle = computed(() => ({
  backgroundColor: props.data.style?.backgroundColor || defaultStyle.value.backgroundColor || '#ffffff',
  borderColor: props.data.style?.borderColor || defaultStyle.value.borderColor || '#409eff',
  color: props.data.style?.textColor || defaultStyle.value.textColor || '#303133',
  fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 13}px`,
  fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'normal',
  borderWidth: `${props.data.style?.borderWidth || defaultStyle.value.borderWidth || 2}px`,
  borderRadius: `${props.data.style?.borderRadius || 6}px`,
}))
</script>

<template>
  <div
    class="flow-node flex items-center justify-center px-5 py-3 border-solid cursor-grab select-none"
    :style="nodeStyle"
  >
    <span class="text-center whitespace-pre-wrap max-w-[180px]">
      {{ data.label }}
    </span>

    <!-- Connection handles -->
    <Handle
      type="target"
      :position="Position.Left"
      class="!bg-blue-500"
    />
    <Handle
      type="source"
      :position="Position.Right"
      class="!bg-blue-500"
    />
  </div>
</template>

<style scoped>
.flow-node {
  min-width: 120px;
  min-height: 50px;
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
