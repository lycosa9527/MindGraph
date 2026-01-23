<script setup lang="ts">
/**
 * StraightEdge - Straight connection edge with arrow for flow maps
 * Direct line connection with optional arrowhead
 */
import { computed } from 'vue'

import { EdgeLabelRenderer, type EdgeProps, getStraightPath } from '@vue-flow/core'

import type { MindGraphEdgeData } from '@/types'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

// Calculate straight path with offset to prevent line from sticking through arrowhead
const path = computed(() => {
  // Calculate distance and angle from source to target
  const dx = props.targetX - props.sourceX
  const dy = props.targetY - props.sourceY
  const distance = Math.sqrt(dx * dx + dy * dy)

  // Offset distance to pull back from target
  // With userSpaceOnUse, refX=12 means arrowhead attaches 12px from end
  // Reduced offset to make arrows stick closer to topic nodes
  const arrowOffset = 10

  // Only apply offset if the path is long enough
  if (distance > arrowOffset) {
    const angle = Math.atan2(dy, dx)
    const adjustedTargetX = props.targetX - Math.cos(angle) * arrowOffset
    const adjustedTargetY = props.targetY - Math.sin(angle) * arrowOffset

    const [edgePath, labelX, labelY] = getStraightPath({
      sourceX: props.sourceX,
      sourceY: props.sourceY,
      targetX: adjustedTargetX,
      targetY: adjustedTargetY,
    })
    return { edgePath, labelX, labelY }
  }

  // Fallback for very short paths
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
      markerWidth="20"
      markerHeight="20"
      refX="12"
      refY="5"
      orient="auto"
      markerUnits="userSpaceOnUse"
    >
      <path
        d="M0,0 L0,10 L15,5 z"
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
