<script setup lang="ts">
/**
 * BoundaryNode - Circle map outer boundary ring
 * Non-interactive visual element showing the constraint boundary
 */
import { computed } from 'vue'

import { useTheme } from '@/composables/useTheme'
import type { MindGraphNodeProps } from '@/types'

const props = defineProps<MindGraphNodeProps>()

// Get theme defaults
const { getNodeStyle } = useTheme({
  diagramType: computed(() => props.data.diagramType),
})

const defaultStyle = computed(() => getNodeStyle('boundary'))

// Get dimensions from style prop (set by diagram store)
// Check both data.style and originalNode.style for width/height
const width = computed(() => {
  const directStyle = props.data.style as { width?: number; height?: number } | undefined
  const originalStyle = props.data.originalNode?.style as
    | { width?: number; height?: number }
    | undefined
  return directStyle?.width || originalStyle?.width || 400
})

const height = computed(() => {
  const directStyle = props.data.style as { width?: number; height?: number } | undefined
  const originalStyle = props.data.originalNode?.style as
    | { width?: number; height?: number }
    | undefined
  return directStyle?.height || originalStyle?.height || 400
})

// Outer circle colors matching old JS bubble-map-renderer.js THEME
// outerCircleStroke: #666666, outerCircleStrokeWidth: 2
const strokeColor = computed(
  () => props.data.style?.borderColor || defaultStyle.value.borderColor || '#666666'
)

const strokeWidth = computed(
  () => props.data.style?.borderWidth || defaultStyle.value.borderWidth || 2
)
</script>

<template>
  <div class="boundary-node pointer-events-none w-full h-full">
    <svg
      class="boundary-svg w-full h-full"
      :viewBox="`0 0 ${width} ${height}`"
      preserveAspectRatio="xMidYMid meet"
    >
      <!-- Perfect circle boundary ring -->
      <circle
        :cx="width / 2"
        :cy="height / 2"
        :r="width / 2 - strokeWidth"
        fill="none"
        :stroke="strokeColor"
        :stroke-width="strokeWidth"
      />
    </svg>
  </div>
</template>

<style scoped>
.boundary-node {
  /* Fill the Vue Flow node wrapper */
  width: 100%;
  height: 100%;
}

.boundary-svg {
  display: block;
  overflow: visible;
}
</style>
