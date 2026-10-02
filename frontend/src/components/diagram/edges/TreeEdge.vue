<script setup lang="ts">
/**
 * TreeEdge - Straight vertical connection edge for tree maps
 * Creates simple vertical lines from bottom of source to top of target
 * No arrowheads - just clean connector lines matching old JS tree-renderer.js
 */
import { computed } from 'vue'

import { type EdgeProps, getStraightPath, useVueFlow } from '@vue-flow/core'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import type { MindGraphEdgeData } from '@/types'
import { nodeSpansCrossingVertical, verticalSegmentsOutsideSpans } from '@/utils/flowVerticalLine'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()
const diagramStore = useDiagramSession()
const { getNodes } = useVueFlow(diagramStore.vueFlowId)

const path = computed(() => {
  const labelX = (props.sourceX + props.targetX) / 2
  const labelY = (props.sourceY + props.targetY) / 2
  const verticalFlow =
    diagramStore.type === 'flow_map' && Math.abs(props.sourceX - props.targetX) <= 2
  if (verticalFlow) {
    const spans = nodeSpansCrossingVertical(
      getNodes.value,
      props.sourceX,
      props.sourceY,
      props.targetY
    )
    if (spans.length > 0) {
      const parts = verticalSegmentsOutsideSpans(props.sourceY, props.targetY, spans)
      const edgePath = parts
        .map((part) => `M ${props.sourceX} ${part.from} L ${props.sourceX} ${part.to}`)
        .join(' ')
      return { edgePath, labelX: props.sourceX, labelY }
    }
  }
  const [edgePath] = getStraightPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
  })
  return { edgePath, labelX, labelY }
})

function nodeIsUnderline(nodeId: string): boolean {
  const node = getNodes.value.find((item) => item.id === nodeId)
  const style = (node?.data as { style?: { nodeShape?: string } } | undefined)?.style
  return style?.nodeShape === 'underline'
}

const edgeStyle = computed(() => ({
  stroke: props.data?.style?.strokeColor || '#ccc', // Light gray for tree connectors
  strokeWidth: props.data?.style?.strokeWidth || 2,
  strokeDasharray: props.data?.style?.strokeDasharray || 'none',
  // A round cap on an underline is not covered by a fill, so the end draws as a thicker knob.
  strokeLinecap: (nodeIsUnderline(props.source) || nodeIsUnderline(props.target)
    ? 'butt'
    : 'round') as 'butt' | 'round',
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
