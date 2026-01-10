<script setup lang="ts">
/**
 * HorizontalStepEdge - Orthogonal step connection edge for horizontal-first paths
 * Creates T-shaped and L-shaped connectors with right-angle turns
 * Used for flow map step-to-substep connections
 *
 * Custom path calculation ensures consistent T-shape:
 * - Horizontal line right from source
 * - Vertical line at midpoint X
 * - Horizontal line to target
 *
 * This is the horizontal version of StepEdge (which goes vertical first)
 */
import { computed } from 'vue'

import { EdgeLabelRenderer, type EdgeProps } from '@vue-flow/core'

import type { MindGraphEdgeData } from '@/types'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

// Calculate custom orthogonal path for 90-degree fork shape
// Path: source -> right to fixed midX -> vertical to targetY -> right to target
// Using fixed offset ensures all substep edges share the same vertical "trunk" line
const path = computed(() => {
  const { sourceX, sourceY, targetX, targetY } = props

  // Use fixed offset from source for the vertical line
  // This creates a clean fork shape where all substeps share the same vertical trunk
  // Offset matches FLOW_SUBSTEP_OFFSET_X / 2 from layoutConfig (half the gap to substeps)
  const forkOffset = 20 // Fixed distance from step node to vertical trunk
  const midX = sourceX + forkOffset

  // Build SVG path: horizontal right to trunk, vertical to target Y, horizontal to target
  let edgePath: string
  if (Math.abs(sourceY - targetY) < 1) {
    // Nodes are horizontally aligned - straight line
    edgePath = `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`
  } else {
    // Create 90-degree fork path
    edgePath = `M ${sourceX} ${sourceY} L ${midX} ${sourceY} L ${midX} ${targetY} L ${targetX} ${targetY}`
  }

  // Label position at midpoint of vertical segment
  const labelX = midX
  const labelY = (sourceY + targetY) / 2

  return { edgePath, labelX, labelY }
})

const edgeStyle = computed(() => ({
  stroke: props.data?.style?.strokeColor || '#888', // Gray color matching old JS
  strokeWidth: props.data?.style?.strokeWidth || 1.5,
  strokeDasharray: props.data?.style?.strokeDasharray || 'none',
}))
</script>

<template>
  <path
    :id="id"
    class="vue-flow__edge-path horizontal-step-edge"
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
.horizontal-step-edge {
  fill: none;
  transition: stroke 0.2s ease;
}

.horizontal-step-edge:hover {
  stroke: #666;
}

.edge-label {
  font-size: 11px;
  white-space: nowrap;
}
</style>
