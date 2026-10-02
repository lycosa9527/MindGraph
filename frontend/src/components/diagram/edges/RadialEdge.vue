<script setup lang="ts">
/**
 * RadialEdge - Center-to-center straight edge for radial layouts
 * Draws a line from the center of source node to center of target node
 * Used for bubble maps where nodes are arranged radially around a center
 *
 * Double bubble map: Connects to the arc (handle) of similarity/difference
 * capsule nodes—the point on the pill facing the topic—instead of the center.
 */
import { computed } from 'vue'

import { type EdgeProps, useVueFlow } from '@vue-flow/core'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import type { MindGraphEdgeData } from '@/types'
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'
import { type NodeShape, shapeRayHitDistance } from '@/utils/nodeShapeStyle'
import { diagramEdgeStrokeStyle } from '@/utils/thinkingMapChrome'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

const diagramStore = useDiagramSession()
const { getNodes } = useVueFlow(diagramStore.vueFlowId)

/** True if target is a double-bubble similarity or difference capsule node */
function isDoubleBubbleCapsuleTarget(targetId: string): boolean {
  if (diagramStore.type !== 'double_bubble_map') return false
  const node = diagramStore.data?.nodes.find((n) => n.id === targetId)
  return Boolean(node && readDoubleBubbleRole(node))
}

// Calculate center-to-center path (or arc-handle path for double-bubble capsules)
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

  const sourceShape = (sourceNode.data?.style as { nodeShape?: NodeShape } | undefined)?.nodeShape
  const sourceHit = shapeRayHitDistance(sourceShape, sourceWidth / 2, sourceHeight / 2, nx, ny)
  const startX = sourceCenterX + nx * sourceHit
  const startY = sourceCenterY + ny * sourceHit

  let endX: number
  let endY: number

  if (isDoubleBubbleCapsuleTarget(props.target)) {
    // Target is a capsule (pill): connect to the arc facing the source
    // Capsule arcs are semicircles at left and right; connect to the arc center on that side
    const targetY = targetNode.position.y
    const capsuleCenterY = targetY + targetHeight / 2
    if (sourceCenterX < targetCenterX) {
      // Source is to the left → connect to left arc (leftmost point of pill)
      endX = targetNode.position.x
      endY = capsuleCenterY
    } else if (sourceCenterX > targetCenterX) {
      // Source is to the right → connect to right arc (rightmost point of pill)
      endX = targetNode.position.x + targetWidth
      endY = capsuleCenterY
    } else {
      // Vertical: use center
      endX = targetCenterX
      endY = targetCenterY
    }
  } else {
    const targetShape = (targetNode.data?.style as { nodeShape?: NodeShape } | undefined)?.nodeShape
    const targetHit = shapeRayHitDistance(targetShape, targetWidth / 2, targetHeight / 2, nx, ny)
    endX = targetCenterX - nx * targetHit
    endY = targetCenterY - ny * targetHit
  }

  const edgePath = `M ${startX} ${startY} L ${endX} ${endY}`
  const labelX = (startX + endX) / 2
  const labelY = (startY + endY) / 2

  return { edgePath, labelX, labelY }
})

const edgeStyle = computed(() =>
  diagramEdgeStrokeStyle(
    props.data?.diagramType,
    props.data?.style?.strokeColor,
    props.data?.style?.strokeWidth,
    '#888888',
    2
  )
)
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
