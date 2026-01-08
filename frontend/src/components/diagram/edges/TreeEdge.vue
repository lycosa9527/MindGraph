<script setup lang="ts">
/**
 * TreeEdge - Straight vertical connection edge for tree maps
 * Creates simple vertical lines from bottom of source to top of target
 * No arrowheads - just clean connector lines matching old JS tree-renderer.js
 */
import { computed } from 'vue'

import { type EdgeProps, getStraightPath } from '@vue-flow/core'

import type { MindGraphEdgeData } from '@/types'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

// Calculate straight path from source bottom to target top
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
  stroke: props.data?.style?.strokeColor || '#ccc', // Light gray for tree connectors
  strokeWidth: props.data?.style?.strokeWidth || 1.5,
  strokeDasharray: props.data?.style?.strokeDasharray || 'none',
}))
</script>

<template>
  <path
    :id="id"
    class="vue-flow__edge-path tree-edge"
    :d="path.edgePath"
    :style="edgeStyle"
  />
</template>

<style scoped>
.tree-edge {
  fill: none;
  transition: stroke 0.2s ease;
}

.tree-edge:hover {
  stroke: #999;
}
</style>
