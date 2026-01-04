<script setup lang="ts">
/**
 * BranchNode - Branch/child node for mind maps and tree maps
 * Represents branches, children, or categories in hierarchical diagrams
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

// Determine if this is a child node (deeper in hierarchy)
const isChild = computed(() => props.data.nodeType === 'branch' && props.data.parentId)

const defaultStyle = computed(() => getNodeStyle(isChild.value ? 'child' : 'branch'))

const nodeStyle = computed(() => ({
  backgroundColor: props.data.style?.backgroundColor || defaultStyle.value.backgroundColor || '#e3f2fd',
  borderColor: props.data.style?.borderColor || defaultStyle.value.borderColor || '#4e79a7',
  color: props.data.style?.textColor || defaultStyle.value.textColor || '#333333',
  fontSize: `${props.data.style?.fontSize || defaultStyle.value.fontSize || 16}px`,
  fontWeight: props.data.style?.fontWeight || defaultStyle.value.fontWeight || 'normal',
  borderWidth: `${props.data.style?.borderWidth || defaultStyle.value.borderWidth || 2}px`,
  borderRadius: `${props.data.style?.borderRadius || 8}px`,
}))
</script>

<template>
  <div
    class="branch-node flex items-center justify-center px-4 py-2 border-solid cursor-grab select-none"
    :style="nodeStyle"
  >
    <span class="text-center whitespace-pre-wrap max-w-[150px]">
      {{ data.label }}
    </span>

    <!-- Connection handles -->
    <Handle
      type="target"
      :position="Position.Left"
      class="!bg-blue-400"
    />
    <Handle
      type="source"
      :position="Position.Right"
      class="!bg-blue-400"
    />
  </div>
</template>

<style scoped>
.branch-node {
  min-width: 80px;
  min-height: 36px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  transition:
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.branch-node:hover {
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.12);
  border-color: #3b82f6;
}

.branch-node:active {
  cursor: grabbing;
}
</style>
