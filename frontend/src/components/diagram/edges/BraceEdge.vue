<script setup lang="ts">
/**
 * BraceEdge - Bracket-style edge for brace maps
 * Creates a curly brace connection for part-whole relationships
 */
import { computed } from 'vue'

import { EdgeLabelRenderer, type EdgeProps } from '@vue-flow/core'

import type { MindGraphEdgeData } from '@/types'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

// Calculate brace path (curly bracket shape)
const path = computed(() => {
  const sx = props.sourceX
  const sy = props.sourceY
  const tx = props.targetX
  const ty = props.targetY

  // Brace control points
  const midX = (sx + tx) / 2
  const braceOffset = 20

  // Create curly brace path
  const edgePath = `
    M ${sx} ${sy}
    L ${sx + braceOffset} ${sy}
    Q ${midX} ${sy} ${midX} ${(sy + ty) / 2}
    Q ${midX} ${ty} ${tx - braceOffset} ${ty}
    L ${tx} ${ty}
  `

  const labelX = midX
  const labelY = (sy + ty) / 2

  return { edgePath: edgePath.trim(), labelX, labelY }
})

const edgeStyle = computed(() => ({
  stroke: props.data?.style?.strokeColor || '#64748b',
  strokeWidth: props.data?.style?.strokeWidth || 2,
  strokeDasharray: props.data?.style?.strokeDasharray || 'none',
}))
</script>

<template>
  <path
    :id="id"
    class="vue-flow__edge-path brace-edge"
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
.brace-edge {
  fill: none;
  transition: stroke 0.2s ease;
}

.brace-edge:hover {
  stroke: #475569;
}

.edge-label {
  font-size: 11px;
  white-space: nowrap;
}
</style>
