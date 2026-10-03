<script setup lang="ts">
/**
 * BoundaryNode - Circle map outer boundary ring
 * Non-interactive visual element showing the constraint boundary
 */
import { computed } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import type { MindGraphNodeProps } from '@/types'
import { thinkingMapStructureColor } from '@/utils/thinkingMapConnectionStroke'

const props = defineProps<MindGraphNodeProps>()
const diagramStore = useDiagramSession()

// Get dimensions from style prop (set by diagram store)
// Check both data.style and originalNode.style for width/height
const width = computed(() => {
  const directStyle = props.data.style as { width?: number; height?: number } | undefined
  const originalStyle = props.data.originalNode?.style as
    { width?: number; height?: number } | undefined
  return directStyle?.width || originalStyle?.width || 400
})

const height = computed(() => {
  const directStyle = props.data.style as { width?: number; height?: number } | undefined
  const originalStyle = props.data.originalNode?.style as
    { width?: number; height?: number } | undefined
  return directStyle?.height || originalStyle?.height || 400
})

const strokeColor = computed(() => thinkingMapStructureColor(diagramStore.data?._mindmap_theme))

const strokeWidth = computed(
  () => props.data.style?.borderWidth || MIND_MAP_GEOMETRY.edgeStrokeWidth
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
        :stroke-opacity="MIND_MAP_GEOMETRY.edgeStrokeOpacity"
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
