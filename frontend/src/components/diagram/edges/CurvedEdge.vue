<script setup lang="ts">
/**
 * CurvedEdge - Curved connection edge for mind maps, tree maps, and concept maps
 * Uses bezier curves for smooth connections
 * Concept map: relationship labels editable on double-click; click segments to toggle arrowheads
 */
import { computed, inject, nextTick, ref, watch } from 'vue'

import { EdgeLabelRenderer, type EdgeProps, getBezierPath, useVueFlow } from '@vue-flow/core'

import { ElIcon } from 'element-plus'

import { Menu } from '@element-plus/icons-vue'

import { getPositionsFromAngle } from '@/composables/diagramCanvas/conceptMapLinkPreviewGeometry'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useTheme } from '@/composables/core/useTheme'
import { CONCEPT_MAP_GENERATING_KEY } from '@/composables/editor/useConceptMapRelationship'
import { useDiagramStore } from '@/stores'
import { useConceptMapRelationshipStore } from '@/stores/conceptMapRelationship'
import type { DiagramType, MindGraphEdgeData } from '@/types'
import { splitBezierPathAtMidpoint } from '@/utils/bezierSplit'
import { isTopicToRootConceptConnection } from '@/utils/conceptMapTopicRootEdge'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

const generatingConnectionIds = inject<{ value: Set<string> }>(
  CONCEPT_MAP_GENERATING_KEY,
  ref(new Set<string>())
)

const diagramStore = useDiagramStore()
const { t } = useLanguage()
const { edges: vueFlowEdges } = useVueFlow()

const isEdgeSelected = computed(() => diagramStore.selectedConnectionId === props.id)

const relationshipPlaceholder = computed(() => t('diagram.relationshipPlaceholder', '输入关系...'))

const isConceptMap = computed(() => (props.data?.diagramType as DiagramType) === 'concept_map')

/** Topic → default root concept (“根概念”): label is fixed; no inline edit */
const isTopicRootLabelLocked = computed(() => {
  if (!isConceptMap.value) return false
  return isTopicToRootConceptConnection(
    { source: props.source, target: props.target },
    diagramStore.data?.nodes
  )
})

const { theme } = useTheme({
  diagramType: computed(() => props.data?.diagramType as DiagramType),
})

const relationshipColor = computed(() => {
  if (!isConceptMap.value) return undefined
  return theme.value?.relationshipColor || '#666666'
})

const isEditing = ref(false)
const editText = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.data?.label,
  (val) => {
    editText.value = val || ''
  },
  { immediate: true }
)

function startEditing() {
  if (!isConceptMap.value || isTopicRootLabelLocked.value) return
  isEditing.value = true
  editText.value = props.data?.label || ''
  useConceptMapRelationshipStore().clearAll()
  nextTick(() => inputRef.value?.focus())
}

function saveLabel() {
  if (!isConceptMap.value || isTopicRootLabelLocked.value) return
  isEditing.value = false
  const trimmed = editText.value.trim()
  if (trimmed !== (props.data?.label || '')) {
    diagramStore.updateConnectionLabel(props.id, trimmed)
    diagramStore.pushHistory('Update relationship')
    if (trimmed === '') {
      eventBus.emit('concept_map:label_cleared', {
        connectionId: props.id,
        sourceId: props.source,
        targetId: props.target,
      })
    }
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    saveLabel()
  }
  if (event.key === 'Escape') {
    isEditing.value = false
    editText.value = props.data?.label || ''
  }
}

function handleLabelClick() {
  if (!isConceptMap.value) return
  if (isEditing.value) return
  diagramStore.selectConnection(props.id)
}

function onRelLinkHandlePointerDown(e: PointerEvent) {
  if (!isConceptMap.value) {
    return
  }
  if (e.button !== 0) {
    return
  }
  if (!e.isPrimary) {
    return
  }
  e.preventDefault()
  e.stopPropagation()
  const p = path.value
  eventBus.emit('concept_map:link_handle_pointer_start', {
    pointerId: e.pointerId,
    clientX: e.clientX,
    clientY: e.clientY,
    connectionId: props.id,
    labelX: p.labelX,
    labelY: p.labelY,
    relSource: props.source,
    relTarget: props.target,
  })
}

// Curvature per diagram type: mindmap uses tighter curves (like double bubble map differences)
const curvature = computed(() => {
  const dt = props.data?.diagramType as DiagramType | undefined
  if (dt === 'mindmap' || dt === 'mind_map') return 0.12
  return 0.25
})

/**
 * When this edge was created by dragging from a relationship label, route the bezier
 * visually FROM that parent label's midpoint instead of the anchor node handle.
 * Uses the parent edge's actual Vue Flow handle positions so the start point matches
 * exactly where the parent label is rendered — no hardcoded node-dimension approximation.
 */
const linkedSourcePos = computed(() => {
  if (!isConceptMap.value) return null
  const parentId = props.data?.linkedFromConnectionId as string | undefined
  if (!parentId) return null
  const parentEdge = vueFlowEdges.value.find((e) => e.id === parentId)
  if (!parentEdge) return null
  const dx = parentEdge.targetX - parentEdge.sourceX
  const dy = parentEdge.targetY - parentEdge.sourceY
  const positions = getPositionsFromAngle(dx, dy)
  const [, labelX, labelY] = getBezierPath({
    sourceX: parentEdge.sourceX,
    sourceY: parentEdge.sourceY,
    sourcePosition: positions.source,
    targetX: parentEdge.targetX,
    targetY: parentEdge.targetY,
    targetPosition: positions.target,
    curvature: 0.25,
  })
  return { x: labelX, y: labelY }
})

// Calculate bezier path
const path = computed(() => {
  const linked = linkedSourcePos.value
  let effectiveSrcX = props.sourceX
  let effectiveSrcY = props.sourceY
  let effectiveSrcPos = props.sourcePosition
  if (linked) {
    effectiveSrcX = linked.x
    effectiveSrcY = linked.y
    const dx = props.targetX - linked.x
    const dy = props.targetY - linked.y
    effectiveSrcPos = getPositionsFromAngle(dx, dy).source
  }
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX: effectiveSrcX,
    sourceY: effectiveSrcY,
    sourcePosition: effectiveSrcPos,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
    curvature: curvature.value,
  })
  // Diagnostic: trace curve connection points for mind map (enable via window.__DEBUG_CURVE_LENGTH__ = true)
  const dt = props.data?.diagramType as DiagramType | undefined
  const debugCurve = (window as unknown as { __DEBUG_CURVE_LENGTH__?: boolean })
    .__DEBUG_CURVE_LENGTH__
  if (import.meta.env.DEV && (dt === 'mindmap' || dt === 'mind_map') && debugCurve) {
    const span = Math.abs(props.targetX - props.sourceX)
    if (props.source === 'topic') {
      const side = props.target.startsWith('branch-l-') ? 'left' : 'right'
      console.log('[CurveDebug] topic-to-branch', {
        target: props.target,
        side,
        sourceX: props.sourceX,
        targetX: props.targetX,
        sourcePosition: props.sourcePosition,
        targetPosition: props.targetPosition,
        horizontalSpan: span,
      })
    } else if (props.source.startsWith('branch-') && props.target.startsWith('branch-')) {
      const side = props.source.startsWith('branch-l-') ? 'left' : 'right'
      console.log('[CurveDebug] branch-to-child', {
        source: props.source,
        target: props.target,
        side,
        sourceX: props.sourceX,
        targetX: props.targetX,
        sourcePosition: props.sourcePosition,
        targetPosition: props.targetPosition,
        horizontalSpan: span,
      })
    }
  }
  return { edgePath, labelX, labelY }
})

const edgeStyle = computed(() => ({
  stroke: props.data?.style?.strokeColor || '#94a3b8',
  strokeWidth: props.data?.style?.strokeWidth || 2,
  strokeDasharray: props.data?.style?.strokeDasharray || 'none',
}))

const HIT_AREA_STROKE = 16
const hitAreaStyle = computed(() => ({
  stroke: 'transparent',
  strokeWidth: HIT_AREA_STROKE,
  fill: 'none',
}))

const isGenerating = computed(
  () => isConceptMap.value && generatingConnectionIds.value.has(props.id)
)

/** True when this edge was created from a relationship-label drag — no label, fixed arrow. */
const isLinkedFromRelationship = computed(
  () => isConceptMap.value && !!(props.data?.linkedFromConnectionId as string | undefined)
)

// Concept map: split path into two segments for clickable arrowhead toggles
// Edges routed from a relationship label use a single fixed-arrow path instead.
const pathSegments = computed(() => {
  if (!isConceptMap.value || isLinkedFromRelationship.value) return null
  const result = splitBezierPathAtMidpoint(path.value.edgePath)
  return result
})

type ArrowheadDirection = 'none' | 'source' | 'target' | 'both'
function normalizeDirection(val: unknown): ArrowheadDirection {
  if (val === 'source' || val === 'target' || val === 'both') return val
  if (val === true) return 'target'
  const raw = val as Record<string, unknown> | undefined
  if (!raw) return 'none'
  const hasTarget =
    raw.targetSegment === true ||
    raw.targetSegment === 'forward' ||
    raw.targetSegment === 'backward'
  const hasSource =
    raw.sourceSegment === true ||
    raw.sourceSegment === 'forward' ||
    raw.sourceSegment === 'backward'
  if (hasSource && hasTarget) return 'both'
  if (hasTarget) return 'target'
  if (hasSource) return 'source'
  return 'none'
}
const arrowheadDirection = computed<ArrowheadDirection>(() => {
  const raw = props.data?.arrowheadDirection ?? props.data?.arrowheadSegments
  return normalizeDirection(raw)
})
const drawTargetArrowhead = computed(
  () => (props.data as { drawTargetArrowhead?: boolean })?.drawTargetArrowhead ?? true
)
const drawSourceArrowheadFlag = computed(
  () => (props.data as { drawSourceArrowhead?: boolean })?.drawSourceArrowhead ?? true
)

const conceptMapMarkerId = computed(() => `arrow-concept-${props.id}`)
const conceptMapMarkerBackwardId = computed(() => `arrow-concept-backward-${props.id}`)

function handleSegmentClick(segment: 'sourceSegment' | 'targetSegment') {
  if (!isConceptMap.value) return
  diagramStore.selectConnection(props.id)
  diagramStore.toggleConnectionArrowhead(props.id, segment)
}

function handleSegment1Click() {
  handleSegmentClick('sourceSegment')
}

function handleSegment2Click() {
  handleSegmentClick('targetSegment')
}

const showSourceArrow = computed(
  () =>
    (arrowheadDirection.value === 'source' || arrowheadDirection.value === 'both') &&
    drawSourceArrowheadFlag.value
)
const showTargetArrow = computed(
  () =>
    (arrowheadDirection.value === 'target' || arrowheadDirection.value === 'both') &&
    drawTargetArrowhead.value
)
const sourceMarkerStart = computed(() =>
  showSourceArrow.value ? `url(#${conceptMapMarkerBackwardId.value})` : undefined
)
const targetMarkerEnd = computed(() =>
  showTargetArrow.value ? `url(#${conceptMapMarkerId.value})` : undefined
)
</script>

<template>
  <!-- Concept map: two segments with clickable arrowhead toggles -->
  <template v-if="isConceptMap && pathSegments">
    <defs>
      <!-- Forward: right-pointing triangle, path connects at refX=10 (1 unit closer to node) -->
      <marker
        :id="conceptMapMarkerId"
        markerWidth="10"
        markerHeight="10"
        refX="8"
        refY="5"
        orient="auto"
        markerUnits="userSpaceOnUse"
      >
        <path
          d="M0,0 L0,10 L10,5 z"
          :fill="edgeStyle.stroke"
        />
      </marker>
      <!-- Backward: left-pointing mirror, path connects at refX=2 (2 units closer to node) -->
      <marker
        :id="conceptMapMarkerBackwardId"
        markerWidth="10"
        markerHeight="10"
        refX="2"
        refY="5"
        orient="auto"
        markerUnits="userSpaceOnUse"
      >
        <path
          d="M10,0 L10,10 L0,5 z"
          :fill="edgeStyle.stroke"
        />
      </marker>
    </defs>
    <!-- Hit area: invisible wider stroke for easier clicking -->
    <path
      :id="`${id}-segment1-hit`"
      class="curved-edge-segment-hit"
      :d="pathSegments.segment1"
      :style="hitAreaStyle"
      pointer-events="stroke"
      cursor="pointer"
      @click.stop="handleSegment1Click"
    />
    <path
      :id="`${id}-segment1`"
      class="vue-flow__edge-path curved-edge curved-edge-segment"
      :d="pathSegments.segment1"
      :style="edgeStyle"
      :marker-start="sourceMarkerStart"
      pointer-events="none"
    />
    <path
      :id="`${id}-segment2-hit`"
      class="curved-edge-segment-hit"
      :d="pathSegments.segment2"
      :style="hitAreaStyle"
      pointer-events="stroke"
      cursor="pointer"
      @click.stop="handleSegment2Click"
    />
    <path
      :id="`${id}-segment2`"
      class="vue-flow__edge-path curved-edge curved-edge-segment"
      :d="pathSegments.segment2"
      :style="edgeStyle"
      :marker-end="targetMarkerEnd"
      pointer-events="none"
    />
  </template>

  <!-- Concept map edge from relationship label: single path with fixed target arrow -->
  <template v-else-if="isLinkedFromRelationship">
    <defs>
      <marker
        :id="conceptMapMarkerId"
        markerWidth="10"
        markerHeight="10"
        refX="8"
        refY="5"
        orient="auto"
        markerUnits="userSpaceOnUse"
      >
        <path
          d="M0,0 L0,10 L10,5 z"
          :fill="edgeStyle.stroke"
        />
      </marker>
    </defs>
    <path
      :id="id"
      class="vue-flow__edge-path curved-edge"
      :d="path.edgePath"
      :style="edgeStyle"
      :marker-end="`url(#${conceptMapMarkerId})`"
    />
  </template>

  <!-- Non-concept map: single path -->
  <path
    v-else
    :id="id"
    class="vue-flow__edge-path curved-edge"
    :d="path.edgePath"
    :style="edgeStyle"
    :marker-end="markerEnd"
  />

  <!-- Edge label: concept map = editable, others = static box.
       Edges linked from a relationship label carry no label of their own. -->
  <EdgeLabelRenderer v-if="data?.label !== undefined && !isLinkedFromRelationship">
    <div
      class="edge-label-wrapper absolute"
      :style="{
        transform: `translate(-50%, -50%) translate(${path.labelX}px, ${path.labelY}px)`,
      }"
    >
      <div
        v-show="isConceptMap && isEdgeSelected && !isEditing"
        class="concept-rel-link-icon concept-rel-link-handle absolute nodrag"
        data-mg-concept-link-handle
        @pointerdown.capture="onRelLinkHandlePointerDown"
      >
        <ElIcon
          :size="20"
          class="text-blue-500 concept-rel-link-icon-inner"
          :data-source-node-id="source"
        >
          <Menu />
        </ElIcon>
      </div>
      <div
        class="edge-label"
        :class="{
          'edge-label-concept-map': isConceptMap,
          'edge-label-box': !isConceptMap,
          'edge-label-selected': isConceptMap && isEdgeSelected,
          'pointer-events-none': !isConceptMap,
          nopan: isConceptMap,
          'cursor-text': isConceptMap && !isEditing && !isTopicRootLabelLocked,
          'cursor-default': isConceptMap && isTopicRootLabelLocked,
        }"
        :style="{
          color: isConceptMap ? relationshipColor : undefined,
          pointerEvents: isConceptMap ? 'auto' : undefined,
        }"
        @click.stop="handleLabelClick"
        @dblclick.stop="startEditing()"
      >
        <span>
          <input
            v-if="isConceptMap && isEditing"
            ref="inputRef"
            v-model="editText"
            type="text"
            class="edge-label-input"
            :placeholder="relationshipPlaceholder"
            @blur="saveLabel"
            @keydown="handleKeydown"
          />
          <span
            v-else
            :class="{
              'edge-label-placeholder': isConceptMap && !data?.label?.trim() && !isGenerating,
            }"
          >
            {{
              data?.label?.trim()
                ? data.label
                : isGenerating
                  ? (t('diagram.aiGenerating', 'AI...') as string)
                  : isConceptMap
                    ? relationshipPlaceholder
                    : ''
            }}
          </span>
        </span>
      </div>
    </div>
  </EdgeLabelRenderer>
</template>

<style scoped>
.curved-edge {
  fill: none;
  transition: stroke 0.2s ease;
}

.curved-edge:hover {
  stroke: #64748b;
}

.curved-edge-segment:hover {
  stroke: #64748b;
}

.curved-edge-segment-hit {
  fill: none;
  transition: none;
}

.edge-label {
  font-size: 11px;
  white-space: nowrap;
}

.edge-label-box {
  background-color: white;
  padding: 4px 8px;
  border-radius: 4px;
  color: #4b5563;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.edge-label-placeholder {
  color: #9ca3af;
}

.dark .edge-label-placeholder {
  color: #6b7280;
}

.edge-label.edge-label-concept-map {
  background: #f5f5f5;
  padding: 4px 8px;
  min-width: 28px;
  min-height: 22px;
  border-radius: 2px;
}

.dark .edge-label-concept-map {
  background: #1f2937;
}

.concept-rel-link-icon {
  bottom: 100%;
  left: 50%;
  margin-bottom: 1px;
  transform: translateX(-50%);
  z-index: 10;
  pointer-events: none;
}

.concept-rel-link-handle {
  touch-action: none;
}

.concept-rel-link-icon-inner {
  pointer-events: auto;
  cursor: grab;
}

.concept-rel-link-icon-inner:active {
  cursor: grabbing;
}

.edge-label.edge-label-concept-map.edge-label-selected {
  outline: 1px solid #3b82f6;
  outline-offset: 1px;
}

.edge-label-input {
  width: 60px;
  min-width: 40px;
  max-width: 100px;
  padding: 2px 4px;
  font-size: 11px;
  border: 1px solid #94a3b8;
  border-radius: 2px;
  background: white;
  color: #333;
  outline: none;
}

.dark .edge-label-input {
  background: #374151;
  border-color: #6b7280;
  color: #e5e7eb;
}
</style>
