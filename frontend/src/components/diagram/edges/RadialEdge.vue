<script setup lang="ts">
/**
 * RadialEdge - Center-to-center straight edge for radial layouts
 * Draws a line from the center of source node to center of target node
 * Used for bubble maps where nodes are arranged radially around a center
 */
import { computed } from 'vue'

import { type EdgeProps, useVueFlow } from '@vue-flow/core'

import type { MindGraphEdgeData } from '@/types'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

const { getNodes } = useVueFlow()

// Calculate center-to-center path
const path = computed(() => {
  const nodes = getNodes.value
  const sourceNode = nodes.find((n) => n.id === props.source)
  const targetNode = nodes.find((n) => n.id === props.target)

  if (!sourceNode || !targetNode) {
    return { edgePath: '', labelX: 0, labelY: 0 }
  }

  // Get node dimensions (use actual dimensions or fallback to common sizes)
  const sourceWidth = sourceNode.dimensions?.width || sourceNode.data?.style?.size || 120
  const sourceHeight = sourceNode.dimensions?.height || sourceNode.data?.style?.size || 120
  const targetWidth = targetNode.dimensions?.width || targetNode.data?.style?.size || 80
  const targetHeight = targetNode.dimensions?.height || targetNode.data?.style?.size || 80

  // Calculate center positions
  const sourceCenterX = sourceNode.position.x + sourceWidth / 2
  const sourceCenterY = sourceNode.position.y + sourceHeight / 2
  const targetCenterX = targetNode.position.x + targetWidth / 2
  const targetCenterY = targetNode.position.y + targetHeight / 2

  // Calculate the direction vector
  const dx = targetCenterX - sourceCenterX
  const dy = targetCenterY - sourceCenterY
  const distance = Math.sqrt(dx * dx + dy * dy)

  if (distance === 0) {
    return { edgePath: '', labelX: sourceCenterX, labelY: sourceCenterY }
  }

  // Normalize direction
  const nx = dx / distance
  const ny = dy / distance

  // Calculate edge of circles (center-to-edge for both source and target)
  const sourceRadius = Math.min(sourceWidth, sourceHeight) / 2
  const targetRadius = Math.min(targetWidth, targetHeight) / 2

  // Start from edge of source circle, end at edge of target circle
  const startX = sourceCenterX + nx * sourceRadius
  const startY = sourceCenterY + ny * sourceRadius
  const endX = targetCenterX - nx * targetRadius
  const endY = targetCenterY - ny * targetRadius

  const edgePath = `M ${startX} ${startY} L ${endX} ${endY}`
  const labelX = (startX + endX) / 2
  const labelY = (startY + endY) / 2

  return { edgePath, labelX, labelY }
})

const edgeStyle = computed(() => ({
  stroke: props.data?.style?.strokeColor || '#888888',
  strokeWidth: props.data?.style?.strokeWidth || 2,
}))
</script>

<template>
  <path
    :id="id"
    class="vue-flow__edge-path radial-edge"
    :d="path.edgePath"
    :style="edgeStyle"
  />
</template>

<style scoped>
.radial-edge {
  fill: none;
  transition: stroke 0.2s ease;
}

.radial-edge:hover {
  stroke: #666666;
}
</style>
