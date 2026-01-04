<script setup lang="ts">
/**
 * CurvedEdge - Curved connection edge for mind maps and tree maps
 * Uses bezier curves for smooth connections
 */
import { computed } from 'vue'

import { EdgeLabelRenderer, type EdgeProps, getBezierPath } from '@vue-flow/core'

import type { MindGraphEdgeData } from '@/types'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

// Calculate bezier path
const path = computed(() => {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
    curvature: 0.25,
  })
  return { edgePath, labelX, labelY }
})

const edgeStyle = computed(() => ({
  stroke: props.data?.style?.strokeColor || '#94a3b8',
  strokeWidth: props.data?.style?.strokeWidth || 2,
  strokeDasharray: props.data?.style?.strokeDasharray || 'none',
}))
</script>

<template>
  <path
    :id="id"
    class="vue-flow__edge-path curved-edge"
    :d="path.edgePath"
    :style="edgeStyle"
    :marker-end="markerEnd"
  />

  <!-- Edge label -->
  <EdgeLabelRenderer v-if="data?.label">
    <div
      class="edge-label absolute bg-white px-2 py-1 rounded text-xs text-gray-600 shadow-sm pointer-events-none"
      :style="{
        transform: `translate(-50%, -50%) translate(${path.labelX}px, ${path.labelY}px)`,
      }"
    >
      {{ data.label }}
    </div>
  </EdgeLabelRenderer>
</template>

<style scoped>
.curved-edge {
  fill: none;
  transition: stroke 0.2s ease;
}

.curved-edge:hover {
  stroke: #64748b;
}

.edge-label {
  font-size: 11px;
  white-space: nowrap;
}
</style>
