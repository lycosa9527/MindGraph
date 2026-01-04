<script setup lang="ts">
/**
 * StraightEdge - Straight connection edge with arrow for flow maps
 * Direct line connection with optional arrowhead
 */
import { computed } from 'vue'

import { EdgeLabelRenderer, type EdgeProps, getStraightPath } from '@vue-flow/core'

import type { MindGraphEdgeData } from '@/types'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

// Calculate straight path
const path = computed(() => {
  const [edgePath, labelX, labelY] = getStraightPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
  })
  return { edgePath, labelX, labelY }
})

const edgeStyle = computed(() => ({
  stroke: props.data?.style?.strokeColor || '#3b82f6',
  strokeWidth: props.data?.style?.strokeWidth || 2,
  strokeDasharray: props.data?.style?.strokeDasharray || 'none',
}))

// Arrow marker ID
const markerId = computed(() => `arrow-${props.id}`)
</script>

<template>
  <!-- Arrow marker definition -->
  <defs>
    <marker
      :id="markerId"
      markerWidth="10"
      markerHeight="10"
      refX="8"
      refY="3"
      orient="auto"
      markerUnits="strokeWidth"
    >
      <path
        d="M0,0 L0,6 L9,3 z"
        :fill="edgeStyle.stroke"
      />
    </marker>
  </defs>

  <path
    :id="id"
    class="vue-flow__edge-path straight-edge"
    :d="path.edgePath"
    :style="edgeStyle"
    :marker-end="`url(#${markerId})`"
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
.straight-edge {
  fill: none;
  transition: stroke 0.2s ease;
}

.straight-edge:hover {
  stroke: #2563eb;
}

.edge-label {
  font-size: 11px;
  white-space: nowrap;
}
</style>
