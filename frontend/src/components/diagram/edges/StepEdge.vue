<script setup lang="ts">
/**
 * StepEdge - Orthogonal step connection edge for tree maps
 * Creates T-shaped and L-shaped connectors with right-angle turns
 * Matches the old JS tree-renderer.js implementation
 *
 * Custom path calculation ensures consistent T-shape:
 * - Vertical line down from source
 * - Horizontal line at midpoint
 * - Vertical line down to target
 */
import { computed } from 'vue'

import { EdgeLabelRenderer, type EdgeProps } from '@vue-flow/core'

import type { MindGraphEdgeData } from '@/types'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

// Calculate custom orthogonal path for consistent T-shape
// Path: source -> down to midY -> horizontal to targetX -> down to target
const path = computed(() => {
  const { sourceX, sourceY, targetX, targetY } = props

  // Calculate midpoint Y for horizontal segment
  // This creates consistent T-shape when multiple edges share the same source
  const midY = sourceY + (targetY - sourceY) / 2

  // Build SVG path: vertical down, horizontal across, vertical down
  let edgePath: string
  if (Math.abs(sourceX - targetX) < 1) {
    // Nodes are vertically aligned - straight line
    edgePath = `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`
  } else {
    // Create orthogonal path with T/L shape
    edgePath = `M ${sourceX} ${sourceY} L ${sourceX} ${midY} L ${targetX} ${midY} L ${targetX} ${targetY}`
  }

  // Label position at midpoint
  const labelX = (sourceX + targetX) / 2
  const labelY = midY

  return { edgePath, labelX, labelY }
})

const edgeStyle = computed(() => ({
  stroke: props.data?.style?.strokeColor || '#bbb', // Gray color from old JS
  strokeWidth: props.data?.style?.strokeWidth || 2,
  strokeDasharray: props.data?.style?.strokeDasharray || 'none',
}))
</script>

<template>
  <path
    :id="id"
    class="vue-flow__edge-path step-edge"
    :d="path.edgePath"
    :style="edgeStyle"
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
.step-edge {
  fill: none;
  transition: stroke 0.2s ease;
}

.step-edge:hover {
  stroke: #999;
}

.edge-label {
  font-size: 11px;
  white-space: nowrap;
}
</style>
