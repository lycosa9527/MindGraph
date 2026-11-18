<script setup lang="ts">
/**
 * StraightEdge - Straight connection edge with arrow for flow maps
 * Direct line connection with optional arrowhead
 */
import { computed } from 'vue'

import { EdgeLabelRenderer, type EdgeProps, getStraightPath } from '@vue-flow/core'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import type { MindGraphEdgeData } from '@/types'
import { FLOW_TOPIC_NODE_ID } from '@/utils/flowMapIdentity'
import { flowTurnEdgePath } from '@/utils/flowTurnEdge'
import { isMultiFlowCauseNode, isMultiFlowEffectNode } from '@/utils/multiFlowMapIdentity'
import { diagramEdgeStrokeStyle } from '@/utils/thinkingMapChrome'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()
const diagramStore = useDiagramSession()

// Check if this is a multi-flow map edge (causes/effects connecting to event)
const isMultiFlowMapEdge = computed(() => {
  if (diagramStore.type !== 'multi_flow_map') return false
  const source = diagramStore.data?.nodes.find((n) => n.id === props.source)
  const target = diagramStore.data?.nodes.find((n) => n.id === props.target)
  const sourceSide = source && (isMultiFlowCauseNode(source) || isMultiFlowEffectNode(source))
  const targetSide = target && (isMultiFlowCauseNode(target) || isMultiFlowEffectNode(target))
  return (
    (Boolean(sourceSide) && props.target === 'event') ||
    (props.source === 'event' && Boolean(targetSide))
  )
})

/** Flow event ↔ first step: plain line, no arrow (all structure modes). */
const isFlowTopicStepEdge = computed(
  () =>
    diagramStore.type === 'flow_map' &&
    (props.source === FLOW_TOPIC_NODE_ID || props.target === FLOW_TOPIC_NODE_ID)
)

const showArrow = computed(() => !isFlowTopicStepEdge.value)

function turnSide(): 'left' | 'right' | null {
  if (props.sourcePosition !== props.targetPosition) return null
  if (props.sourcePosition === 'right' || props.sourcePosition === 'left') {
    return props.sourcePosition
  }
  return null
}

function axisAlignedTopicStepPath(): {
  edgePath: string
  labelX: number
  labelY: number
} | null {
  if (!isFlowTopicStepEdge.value) return null
  const horizontal =
    props.sourcePosition === 'right' ||
    props.sourcePosition === 'left' ||
    props.targetPosition === 'left' ||
    props.targetPosition === 'right'
  if (horizontal) {
    // True horizontal bar between event and step (row / stack structures).
    const y = (props.sourceY + props.targetY) / 2
    const [edgePath, labelX, labelY] = getStraightPath({
      sourceX: props.sourceX,
      sourceY: y,
      targetX: props.targetX,
      targetY: y,
    })
    return { edgePath, labelX, labelY }
  }
  // Vertical structure: spine drop without arrow tip inset.
  const x = (props.sourceX + props.targetX) / 2
  const [edgePath, labelX, labelY] = getStraightPath({
    sourceX: x,
    sourceY: props.sourceY,
    targetX: x,
    targetY: props.targetY,
  })
  return { edgePath, labelX, labelY }
}

// Calculate straight path with offset to prevent line from sticking through arrowhead
const path = computed(() => {
  const topicStep = axisAlignedTopicStepPath()
  if (topicStep) return topicStep

  const turn = turnSide()
  const arrowOffset = showArrow.value ? (isMultiFlowMapEdge.value ? 7 : 10) : 0
  if (turn) {
    return flowTurnEdgePath(
      props.sourceX,
      props.sourceY,
      props.targetX,
      props.targetY,
      turn,
      arrowOffset
    )
  }

  // Calculate distance and angle from source to target
  const dx = props.targetX - props.sourceX
  const dy = props.targetY - props.sourceY
  const distance = Math.sqrt(dx * dx + dy * dy)

  // Only apply offset if the path is long enough
  if (arrowOffset > 0 && distance > arrowOffset) {
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

function nodeIsUnderline(nodeId: string): boolean {
  const node = diagramStore.data?.nodes.find((item) => item.id === nodeId)
  return node?.style?.nodeShape === 'underline'
}

const edgeStyle = computed(() => ({
  ...diagramEdgeStrokeStyle(
    props.data?.diagramType,
    props.data?.style?.strokeColor,
    props.data?.style?.strokeWidth,
    '#3b82f6',
    2
  ),
  strokeDasharray: props.data?.style?.strokeDasharray || 'none',
  // A round cap on an underline is not covered by a fill, so the end draws as a thicker knob.
  strokeLinecap: (nodeIsUnderline(props.source) || nodeIsUnderline(props.target)
    ? 'butt'
    : 'round') as 'butt' | 'round',
}))

// Arrow marker ID
const markerId = computed(() => `arrow-${props.id}`)
</script>

<template>
  <!-- Arrow marker definition -->
  <defs v-if="showArrow">
    <marker
      :id="markerId"
      markerWidth="20"
      markerHeight="20"
      :refX="isMultiFlowMapEdge ? 10 : 12"
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
    :class="{ 'is-topic-step': isFlowTopicStepEdge }"
    :d="path.edgePath"
    :style="edgeStyle"
    :marker-end="showArrow ? `url(#${markerId})` : undefined"
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
