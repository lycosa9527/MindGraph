<script setup lang="ts">
/**
 * MindMapOrthogonalEdge — 2px orthogonal connectors (0.7 opacity; 3px on hover).
 */
import { computed, ref } from 'vue'

import { type EdgeProps, useVueFlow } from '@vue-flow/core'

import type { MindGraphEdgeData, MindGraphNodeData, NodeStyle } from '@/types'
import { useMindMapExportOutlineWireframeActive } from '@/composables/mindMap/useMindMapExportOutlineWireframe'
import { useDiagramStore } from '@/stores'
import { resolveMindMapOutlineWireframeEdgeStroke } from '@/utils/mindMapOutlineWireframeStyle'
import {
  MIND_MAP_GEOMETRY,
  MINDMAP_UNDERLINE_STROKE_WIDTH,
  mindMapConnectionAnchorY,
  resolveMindMapTopicBorderColor,
} from '@/config/mindMapGeometry'
import {
  buildMindMapBracketBusPath,
  computeMindMapSharedTrunkX,
} from '@/utils/mindMapOrthogonalPath'
import {
  mindMapBranchSide,
  resolveMindMapEdgeEndpoint,
  resolveMindMapNodeStyle,
} from '@/utils/mindMapEdgeEndpoints'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

const isHovered = ref(false)

const { edges: vueFlowEdges, nodes: vueFlowNodes } = useVueFlow()

const diagramStore = useDiagramStore()
const exportOutlineActive = useMindMapExportOutlineWireframeActive()
const preservedNodeStyles = computed(
  () => (diagramStore.data?._node_styles ?? {}) as Record<string, NodeStyle>
)

/** Mind-map layout measurements — same source as recalculateMindMapV2ColumnPositions. */
const mindMapWidths = computed(
  () => diagramStore.mindMapNodeWidths as Record<string, number>
)
const mindMapHeights = computed(
  () => diagramStore.mindMapNodeHeights as Record<string, number>
)
const fallbackDimensions = computed(
  () => diagramStore.nodeDimensions as Record<string, { width: number; height: number }>
)

function measuredSize(nodeId: string | undefined): { width: number; height: number } | undefined {
  if (!nodeId) return undefined
  const w = mindMapWidths.value[nodeId]
  const h = mindMapHeights.value[nodeId]
  const fallback = fallbackDimensions.value[nodeId]
  if (w === undefined && h === undefined && !fallback) return undefined
  return {
    width: w ?? fallback?.width,
    height: h ?? fallback?.height,
  }
}

const diagramStyleId = computed(
  () => diagramStore.data?._mindmap_diagram_style as string | undefined
)

function nodeShape(
  node: (typeof vueFlowNodes.value)[number] | undefined,
  style: NodeStyle | undefined
) {
  if (!node) return 'rounded' as const
  return resolveMindMapNodeShape(
    {
      id: node.id,
      type: node.id === 'topic' ? 'topic' : 'branch',
      style,
    },
    diagramStyleId.value
  )
}

function edgeEndpoint(
  node: (typeof vueFlowNodes.value)[number] | undefined,
  role: 'source' | 'target',
  fallback: { x: number; y: number }
) {
  const style = resolveMindMapNodeStyle(node?.id, node?.data as MindGraphNodeData | undefined, preservedNodeStyles.value)
  return resolveMindMapEdgeEndpoint(
    node,
    role,
    fallback,
    style,
    measuredSize(node?.id),
    diagramStyleId.value
  )
}

const isFromTopic = computed(() => props.source === 'topic')

function branchSide(nodeId: string | undefined): 'left' | 'right' | null {
  return mindMapBranchSide(nodeId)
}

const siblingEdges = computed(() =>
  vueFlowEdges.value.filter((edge) => {
    if (edge.source !== props.source) return false
    if (isFromTopic.value) {
      const mySide = branchSide(props.target)
      const theirSide = branchSide(edge.target)
      return mySide != null && mySide === theirSide
    }
    return true
  })
)

const topicAnchor = computed(() => {
  if (!isFromTopic.value) return null
  const topicNode = vueFlowNodes.value.find((n) => n.id === 'topic')
  if (!topicNode?.position) return null

  const topicMeasured = measuredSize('topic')
  const w =
    topicMeasured?.width ??
    topicNode.dimensions?.width ??
    (topicNode.data?.estimatedWidth as number | undefined) ??
    120
  const h =
    topicMeasured?.height ??
    topicNode.dimensions?.height ??
    (topicNode.data?.estimatedHeight as number | undefined) ??
    48

  const topicStyle = resolveMindMapNodeStyle(
    'topic',
    topicNode.data as MindGraphNodeData | undefined,
    preservedNodeStyles.value
  )
  const shape = nodeShape(topicNode, topicStyle)
  const side = branchSide(props.target)
  const baseX = side === 'left' ? topicNode.position.x : topicNode.position.x + w

  return edgeEndpoint(topicNode, 'source', {
    x: baseX,
    y: mindMapConnectionAnchorY(topicNode.position.y, h, shape),
  })
})

const sourceNode = computed(() => vueFlowNodes.value.find((n) => n.id === props.source))
const targetNode = computed(() => vueFlowNodes.value.find((n) => n.id === props.target))

const anchorPoint = computed(() => {
  if (topicAnchor.value) {
    return topicAnchor.value
  }
  return edgeEndpoint(sourceNode.value, 'source', {
    x: props.sourceX,
    y: props.sourceY,
  })
})

function resolveTargetPoint(
  node: (typeof vueFlowNodes.value)[number] | undefined,
  fallback: { x: number; y: number }
) {
  return edgeEndpoint(node, 'target', fallback)
}

const targetPoint = computed(() =>
  resolveTargetPoint(targetNode.value, {
    x: props.targetX,
    y: props.targetY,
  })
)

const siblingTargetYs = computed(() =>
  siblingEdges.value.map((edge) => {
    const node = vueFlowNodes.value.find((n) => n.id === edge.target)
    return resolveTargetPoint(node, {
      x: edge.targetX ?? props.targetX,
      y: edge.targetY ?? props.targetY,
    }).y
  })
)

const siblingTargetXs = computed(() =>
  siblingEdges.value.map((edge) => {
    const node = vueFlowNodes.value.find((n) => n.id === edge.target)
    return edgeEndpoint(node, 'target', {
      x: edge.targetX ?? props.targetX,
      y: edge.targetY ?? props.targetY,
    }).x
  })
)

/** One edge per sibling group draws the shared vertical spine + stem. */
const drawsBusSpine = computed(() => {
  const siblings = siblingEdges.value
  if (siblings.length <= 1) return true
  const sorted = [...siblings].sort((a, b) => String(a.id).localeCompare(String(b.id)))
  return sorted[0]?.id === props.id
})

const sharedTrunkX = computed(() => {
  return computeMindMapSharedTrunkX(anchorPoint.value.x, siblingTargetXs.value, targetPoint.value.x)
})

const targetNodeStyle = computed(() =>
  resolveMindMapNodeStyle(
    targetNode.value?.id,
    targetNode.value?.data as MindGraphNodeData | undefined,
    preservedNodeStyles.value
  )
)

const targetShape = computed(() => nodeShape(targetNode.value, targetNodeStyle.value))

const isSingleUnderlineChild = computed(
  () => siblingTargetYs.value.length === 1 && targetShape.value === 'underline'
)

const isSingleTopicSideChild = computed(
  () => isFromTopic.value && siblingEdges.value.length === 1
)

const path = computed(() => {
  const from = anchorPoint.value
  const to = targetPoint.value
  const trunkX = sharedTrunkX.value
  const ys = siblingTargetYs.value

  const edgePath = buildMindMapBracketBusPath(
    from.x,
    from.y,
    to.x,
    to.y,
    trunkX,
    ys,
    {
      drawSpine: drawsBusSpine.value,
      siblingToXs: siblingTargetXs.value,
      singleUnderlineChild: isSingleUnderlineChild.value,
      singleTopicSideChild: isSingleTopicSideChild.value,
    }
  )

  return {
    edgePath,
    labelX: trunkX,
    labelY: (from.y + to.y) / 2,
  }
})

const topicBorderColor = computed(() => {
  const topic = vueFlowNodes.value.find((n) => n.id === 'topic')
  const fromTopic = (topic?.data as MindGraphNodeData | undefined)?.style?.borderColor
  return fromTopic || resolveMindMapTopicBorderColor(null)
})

const edgeStrokeColor = computed(() =>
  exportOutlineActive.value ? resolveMindMapOutlineWireframeEdgeStroke() : topicBorderColor.value
)

const edgeStyle = computed(() => ({
  fill: 'none',
  stroke: edgeStrokeColor.value,
  strokeWidth: isHovered.value
    ? MIND_MAP_GEOMETRY.edgeStrokeWidthHover
    : (props.data?.style?.strokeWidth ?? MIND_MAP_GEOMETRY.edgeStrokeWidth),
  strokeOpacity: exportOutlineActive.value || isHovered.value ? 1 : MIND_MAP_GEOMETRY.edgeStrokeOpacity,
  strokeDasharray: props.data?.style?.strokeDasharray || 'none',
  strokeLinecap: 'butt' as const,
  strokeLinejoin: 'round' as const,
  transition: 'stroke-width 0.15s ease, stroke-opacity 0.15s ease',
}))

/**
 * Underline bar for the target node, drawn here (in the SVG edge layer) instead of as an
 * HTML div in the node. Sharing the connector's SVG coordinate space means the join can
 * never seam under the fractional viewport transform (HTML and SVG layers snap to device
 * pixels independently). Spans the full node width at the same midline Y the connector
 * targets. The topic (no incoming edge) still paints its own HTML bar.
 */
const underlineBar = computed(() => {
  if (targetShape.value !== 'underline') return null
  const node = targetNode.value
  if (!node?.position) return null
  const size = measuredSize(node.id)
  const w =
    size?.width ??
    node.dimensions?.width ??
    (node.data?.estimatedWidth as number | undefined) ??
    MIND_MAP_GEOMETRY.minWidth
  const y = targetPoint.value.y
  return { d: `M ${node.position.x} ${y} L ${node.position.x + w} ${y}` }
})

const underlineBarStyle = computed(() => ({
  fill: 'none',
  stroke: edgeStrokeColor.value,
  strokeWidth: MINDMAP_UNDERLINE_STROKE_WIDTH,
  strokeOpacity: exportOutlineActive.value ? 1 : MIND_MAP_GEOMETRY.edgeStrokeOpacity,
  strokeLinecap: 'butt' as const,
}))
</script>

<template>
  <path
    :id="id"
    class="vue-flow__edge-path mindmap-orthogonal-edge"
    :d="path.edgePath"
    fill="none"
    :style="edgeStyle"
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
  />
  <path
    v-if="underlineBar"
    class="mindmap-underline-bar"
    :d="underlineBar.d"
    fill="none"
    :style="underlineBarStyle"
  />
</template>

<style scoped>
.mindmap-orthogonal-edge {
  fill: none;
  cursor: pointer;
}
</style>
