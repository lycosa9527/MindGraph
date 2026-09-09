<script setup lang="ts">
/**
 * Association overlay, 概要-style three-dot handle, and style toolbar.
 */
import { computed, ref, toValue } from 'vue'

import { EdgeLabelRenderer, useVueFlow } from '@vue-flow/core'

import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import {
  associationCurveDrag,
  associationLineHoverId,
  associationLineToolbarId,
  setAssociationLineHover,
  setAssociationLineToolbar,
  useMindMapAssociationLine,
} from '@/composables/mindMap/useMindMapAssociationLine'
import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'
import { parseCubicBezierPath } from '@/utils/bezierSplit'
import {
  associationChromePointAwayFromLabel,
  associationCurveOffsetFromApex,
  associationEndsFromArrowhead,
} from '@/utils/mindMapAssociationLine'

import MindMapAssociationFloatingToolbar from './MindMapAssociationFloatingToolbar.vue'

const HANDLE_ON_PATH_T = 0.28
const DELETE_ON_PATH_T = 0.72
const LABEL_CLEARANCE_PX = 48
const CURVE_DRAG_THRESHOLD_PX = 5
const TOOLBAR_GAP = 14
const TOOLBAR_EST_W = 280
const TOOLBAR_EST_H = 168

const props = defineProps<{
  connectionId: string
  edgePath: string
  labelX: number
  labelY: number
  stroke: string
  strokeWidth: number
  strokeDasharray: string
  selected: boolean
  arrowheadDirection?: 'none' | 'source' | 'target' | 'both'
}>()

const { t } = useLanguage()
const diagramStore = useDiagramSession()
useMindMapAssociationLine()
const { viewport, screenToFlowCoordinate } = useVueFlow(diagramStore.vueFlowId)

const dragPointerId = ref<number | null>(null)
const dragOriginClient = ref<{ x: number; y: number } | null>(null)
const dragEnds = ref<{ source: { x: number; y: number }; target: { x: number; y: number } } | null>(
  null
)
const dragMoved = ref(false)

const canEdit = computed(
  () => !diagramPresentationReadOnlyRef.value && !toValue(diagramStore.isReadonly)
)

const arrows = computed(() => associationEndsFromArrowhead(props.arrowheadDirection))
const toolbarOpen = computed(() => associationLineToolbarId.value === props.connectionId)
const curveDragging = computed(() => associationCurveDrag.value?.id === props.connectionId)
const showChrome = computed(
  () =>
    canEdit.value &&
    (props.selected ||
      toolbarOpen.value ||
      curveDragging.value ||
      associationLineHoverId.value === props.connectionId)
)
const showDelete = computed(() => showChrome.value)

const handlePoint = computed(() => {
  if (curveDragging.value) {
    return { x: props.labelX, y: props.labelY }
  }
  return associationChromePointAwayFromLabel(
    props.edgePath,
    { x: props.labelX, y: props.labelY },
    HANDLE_ON_PATH_T,
    LABEL_CLEARANCE_PX
  )
})

const deletePoint = computed(() =>
  associationChromePointAwayFromLabel(
    props.edgePath,
    { x: props.labelX, y: props.labelY },
    DELETE_ON_PATH_T,
    LABEL_CLEARANCE_PX
  )
)

const handleStyle = computed(() => ({
  transform: `translate(-50%, -50%) translate(${handlePoint.value.x}px, ${handlePoint.value.y}px)`,
  '--mm-summary-disk': '16px',
  '--mm-summary-stroke': props.stroke,
}))

const deleteStyle = computed(() => ({
  transform: `translate(-50%, -50%) translate(${deletePoint.value.x}px, ${deletePoint.value.y}px)`,
}))

const toolbarAnchor = computed(() => {
  if (!toolbarOpen.value || typeof window === 'undefined') return null
  void viewport.value
  void handlePoint.value
  const handle = document.querySelector(
    `[data-mg-assoc-handle="${props.connectionId}"]`
  )
  if (!(handle instanceof HTMLElement)) return null
  const rect = handle.getBoundingClientRect()
  let left = rect.right + TOOLBAR_GAP
  let top = rect.top - 12
  if (left + TOOLBAR_EST_W > window.innerWidth - 8) {
    left = rect.left - TOOLBAR_GAP - TOOLBAR_EST_W
  }
  left = Math.min(Math.max(8, left), window.innerWidth - TOOLBAR_EST_W - 8)
  top = Math.min(Math.max(8, top), window.innerHeight - TOOLBAR_EST_H - 8)
  return { left, top }
})

const endMarker = computed(() =>
  arrows.value.end ? `url(#assoc-arrow-end-${props.connectionId})` : undefined
)
const startMarker = computed(() =>
  arrows.value.start ? `url(#assoc-arrow-start-${props.connectionId})` : undefined
)

function onLineEnter(): void {
  setAssociationLineHover(props.connectionId)
}

function onLineLeave(): void {
  setAssociationLineHover(null)
}

function openToolbar(): void {
  if (!canEdit.value) return
  if (associationLineToolbarId.value === props.connectionId) {
    setAssociationLineToolbar(null)
    return
  }
  diagramStore.clearSelection()
  diagramStore.selectConnection(props.connectionId)
  setAssociationLineToolbar(props.connectionId)
}

function onHandlePointerDown(event: PointerEvent): void {
  event.preventDefault()
  event.stopPropagation()
  if (!canEdit.value || event.button !== 0) return
  const ends = parseCubicBezierPath(props.edgePath)
  if (!ends) return
  dragPointerId.value = event.pointerId
  dragOriginClient.value = { x: event.clientX, y: event.clientY }
  dragEnds.value = { source: ends[0], target: ends[3] }
  dragMoved.value = false
  setAssociationLineHover(props.connectionId)
  if (event.currentTarget instanceof HTMLElement) {
    event.currentTarget.setPointerCapture(event.pointerId)
  }
}

function onHandlePointerMove(event: PointerEvent): void {
  if (dragPointerId.value !== event.pointerId || !dragOriginClient.value || !dragEnds.value) {
    return
  }
  const dx = event.clientX - dragOriginClient.value.x
  const dy = event.clientY - dragOriginClient.value.y
  if (!dragMoved.value && dx * dx + dy * dy < CURVE_DRAG_THRESHOLD_PX ** 2) return
  dragMoved.value = true
  setAssociationLineToolbar(null)
  const apex = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  associationCurveDrag.value = {
    id: props.connectionId,
    offset: associationCurveOffsetFromApex(dragEnds.value.source, dragEnds.value.target, apex),
  }
}

function finishHandleGesture(event: PointerEvent): void {
  if (dragPointerId.value !== event.pointerId) return
  const moved = dragMoved.value
  const live = associationCurveDrag.value
  dragPointerId.value = null
  dragOriginClient.value = null
  dragEnds.value = null
  dragMoved.value = false
  const handle = event.currentTarget
  if (handle instanceof HTMLElement && handle.hasPointerCapture(event.pointerId)) {
    handle.releasePointerCapture(event.pointerId)
  }
  if (event.type === 'pointercancel') {
    associationCurveDrag.value = null
    return
  }
  if (moved && live?.id === props.connectionId) {
    diagramStore.updateConnectionChrome(props.connectionId, { curveOffset: live.offset })
    associationCurveDrag.value = null
    return
  }
  associationCurveDrag.value = null
  if (event.detail === 2) return
  openToolbar()
}

function deleteLine(event: MouseEvent): void {
  event.preventDefault()
  event.stopPropagation()
  setAssociationLineToolbar(null)
  diagramStore.removeConceptMapConnection(props.connectionId)
}
</script>

<template>
  <EdgeLabelRenderer>
    <svg
      class="mg-association-overlay absolute overflow-visible"
      style="left: 0; top: 0; width: 1px; height: 1px; pointer-events: none"
    >
      <defs>
        <marker
          :id="`assoc-arrow-end-${connectionId}`"
          markerWidth="10"
          markerHeight="10"
          refX="8"
          refY="5"
          orient="auto"
          markerUnits="userSpaceOnUse"
        >
          <path
            d="M0,0 L0,10 L10,5 z"
            :fill="stroke"
          />
        </marker>
        <marker
          :id="`assoc-arrow-start-${connectionId}`"
          markerWidth="10"
          markerHeight="10"
          refX="2"
          refY="5"
          orient="auto"
          markerUnits="userSpaceOnUse"
        >
          <path
            d="M10,0 L10,10 L0,5 z"
            :fill="stroke"
          />
        </marker>
      </defs>
      <path
        class="mg-association-hit"
        :d="edgePath"
        fill="none"
        stroke="transparent"
        stroke-width="18"
        pointer-events="stroke"
        @pointerenter="onLineEnter"
        @pointerleave="onLineLeave"
      />
      <path
        class="mg-association-stroke"
        :d="edgePath"
        fill="none"
        :stroke="stroke"
        :stroke-width="strokeWidth"
        :stroke-dasharray="strokeDasharray"
        stroke-linecap="round"
        :marker-start="startMarker"
        :marker-end="endMarker"
        pointer-events="none"
      />
    </svg>
    <button
      v-show="showChrome"
      type="button"
      class="mm-summary-handle-btn nodrag nopan absolute"
      :class="{ 'is-selected': toolbarOpen || selected, 'is-dragging': curveDragging }"
      :data-mg-assoc-handle="connectionId"
      :style="handleStyle"
      :title="t('canvas.floatingToolbar.assocCurveDrag', 'Drag to bend the curve')"
      :aria-label="t('canvas.floatingToolbar.assocCurveDrag', 'Drag to bend the curve')"
      @pointerenter="onLineEnter"
      @pointerleave="onLineLeave"
      @pointerdown.stop="onHandlePointerDown"
      @pointermove.stop="onHandlePointerMove"
      @pointerup.stop="finishHandleGesture"
      @pointercancel.stop="finishHandleGesture"
      @dblclick.stop.prevent="deleteLine"
    >
      <span class="mm-summary-handle-btn__disk" />
      <span class="mm-summary-handle-btn__dots">
        <span />
        <span />
        <span />
      </span>
    </button>
    <button
      v-show="showDelete"
      type="button"
      class="mg-association-delete nodrag nopan absolute"
      :style="deleteStyle"
      :aria-label="t('canvas.ribbon.assocLineDelete', 'Delete relationship line')"
      @pointerenter="onLineEnter"
      @pointerleave="onLineLeave"
      @click.stop="deleteLine"
    >
      <svg
        viewBox="0 0 20 20"
        width="18"
        height="18"
        aria-hidden="true"
      >
        <circle
          cx="10"
          cy="10"
          r="8.25"
        />
        <path d="M7 7l6 6M13 7l-6 6" />
      </svg>
    </button>
    <MindMapAssociationFloatingToolbar
      v-if="toolbarAnchor"
      :connection-id="connectionId"
      :left="toolbarAnchor.left"
      :top="toolbarAnchor.top"
    />
  </EdgeLabelRenderer>
</template>

<style scoped>
.mm-summary-handle-btn {
  z-index: 12;
  width: 22px;
  height: 22px;
  padding: 0;
  border: none;
  background: transparent;
  pointer-events: auto;
  cursor: grab;
  touch-action: none;
}

.mm-summary-handle-btn.is-dragging {
  cursor: grabbing;
}

.mm-summary-handle-btn__disk {
  position: absolute;
  left: 50%;
  top: 50%;
  width: var(--mm-summary-disk);
  height: var(--mm-summary-disk);
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: var(--mm-summary-stroke);
}

.mm-summary-handle-btn.is-selected .mm-summary-handle-btn__disk {
  box-shadow: 0 0 0 1.5px #2563eb;
}

.mm-summary-handle-btn__dots {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  pointer-events: none;
}

.mm-summary-handle-btn__dots span {
  width: 2.4px;
  height: 2.4px;
  border-radius: 50%;
  background: #fff;
}

.mg-association-delete {
  z-index: 12;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  pointer-events: auto;
}

.mg-association-delete svg {
  display: block;
}

.mg-association-delete circle {
  fill: #ffffff;
  stroke: #64748b;
  stroke-width: 1.5;
}

.mg-association-delete path {
  fill: none;
  stroke: #64748b;
  stroke-width: 1.7;
  stroke-linecap: round;
}

.mg-association-delete:hover circle {
  fill: #fef2f2;
  stroke: #dc2626;
}

.mg-association-delete:hover path {
  stroke: #dc2626;
}

.dark .mg-association-delete circle {
  fill: #1f2937;
  stroke: #94a3b8;
}

.dark .mg-association-delete path {
  stroke: #94a3b8;
}

.dark .mg-association-delete:hover circle {
  fill: #450a0a;
  stroke: #f87171;
}

.dark .mg-association-delete:hover path {
  stroke: #f87171;
}
</style>
