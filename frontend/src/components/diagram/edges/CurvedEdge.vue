<script setup lang="ts">
/**
 * CurvedEdge - Curved connection edge for mind maps, tree maps, and concept maps
 * Uses bezier curves for smooth connections
 * Concept map: relationship labels editable on double-click; click segments to toggle arrowheads
 */
import { computed, inject, nextTick, ref, watch } from 'vue'

import { EdgeLabelRenderer, type EdgeProps, getBezierPath } from '@vue-flow/core'

import { CONCEPT_MAP_GENERATING_KEY } from '@/composables/useConceptMapRelationship'
import { eventBus } from '@/composables/useEventBus'
import { useLanguage } from '@/composables/useLanguage'
import { useTheme } from '@/composables/useTheme'
import { useConceptMapRelationshipStore } from '@/stores/conceptMapRelationship'
import { useDiagramStore } from '@/stores'
import type { DiagramType, MindGraphEdgeData } from '@/types'
import { splitBezierPathAtMidpoint } from '@/utils/bezierSplit'

const props = defineProps<EdgeProps<MindGraphEdgeData>>()

const generatingConnectionIds = inject<{ value: Set<string> }>(
  CONCEPT_MAP_GENERATING_KEY,
  ref(new Set<string>())
)

const diagramStore = useDiagramStore()
const { t } = useLanguage()

const relationshipPlaceholder = computed(() => t('diagram.relationshipPlaceholder', '输入关系...'))

const isConceptMap = computed(() => (props.data?.diagramType as DiagramType) === 'concept_map')

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
  if (!isConceptMap.value) return
  isEditing.value = true
  editText.value = props.data?.label || ''
  useConceptMapRelationshipStore().clearAll()
  nextTick(() => inputRef.value?.focus())
}

function saveLabel() {
  if (!isConceptMap.value) return
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

// Calculate bezier path
const path = computed(() => {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
    curvature: 0.25,
  })
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


// Concept map: split path into two segments for clickable arrowhead toggles
const pathSegments = computed(() => {
  if (!isConceptMap.value) return null
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

const conceptMapMarkerId = computed(() => `arrow-concept-${props.id}`)
const conceptMapMarkerBackwardId = computed(() => `arrow-concept-backward-${props.id}`)

function handleSegmentClick(segment: 'sourceSegment' | 'targetSegment') {
  if (!isConceptMap.value) return
  diagramStore.toggleConnectionArrowhead(props.id, segment)
}

function handleSegment1Click() {
  handleSegmentClick('sourceSegment')
}

function handleSegment2Click() {
  handleSegmentClick('targetSegment')
}

const showSourceArrow = computed(
  () => arrowheadDirection.value === 'source' || arrowheadDirection.value === 'both'
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

  <!-- Non-concept map: single path -->
  <path
    v-else
    :id="id"
    class="vue-flow__edge-path curved-edge"
    :d="path.edgePath"
    :style="edgeStyle"
    :marker-end="markerEnd"
  />

  <!-- Edge label: concept map = editable, others = static box -->
  <EdgeLabelRenderer v-if="data?.label !== undefined">
    <div
      class="edge-label-wrapper absolute"
      :style="{
        transform: `translate(-50%, -50%) translate(${path.labelX}px, ${path.labelY}px)`,
      }"
    >
      <div
        class="edge-label"
        :class="{
          'edge-label-concept-map': isConceptMap,
          'edge-label-box': !isConceptMap,
          'pointer-events-none': !isConceptMap,
          nopan: isConceptMap,
          'cursor-text': isConceptMap && !isEditing,
        }"
        :style="{
          color: isConceptMap ? relationshipColor : undefined,
          pointerEvents: isConceptMap ? 'auto' : undefined,
        }"
        @dblclick.stop="startEditing"
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
            :class="{ 'edge-label-placeholder': isConceptMap && !data?.label?.trim() && !isGenerating }"
          >
            {{
              isGenerating
                ? (t('diagram.aiGenerating', 'AI...') as string)
                : isConceptMap && !data?.label?.trim()
                  ? relationshipPlaceholder
                  : data?.label || ''
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
