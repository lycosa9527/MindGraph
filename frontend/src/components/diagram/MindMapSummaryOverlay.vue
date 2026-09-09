<script setup lang="ts">
/**
 * V2 canvas overlay: range rect, summary brace, handle, and style toolbar.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import {
  type SummaryRangeDrag,
  useMindMapSummaryRangeDrag,
} from '@/composables/mindMap/useMindMapSummaryRangeDrag'
import { getMindMapThemeForDiagram } from '@/config/mindMapThemes'
import {
  coveredBoxesForSummary,
  siblingBoxesForSummary,
} from '@/stores/diagram/mindMapSummaryLayout'
import { isSessionMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'
import {
  mindMapSummaryRootNodeId,
  mindMapSummaryStrokeDasharray,
  readMindMapSummaries,
  resolveMindMapSummaryKind,
  resolveMindMapSummaryLineStyle,
  resolveMindMapSummaryStrokeWidth,
} from '@/utils/mindMapSummary'
import {
  mindMapSummaryBracePath,
  mindMapSummaryConnectorPath,
  mindMapSummaryPaddedRangeRect,
} from '@/utils/mindMapSummaryBrace'

import MindMapSummaryFloatingToolbar from './MindMapSummaryFloatingToolbar.vue'

const HANDLE_R = 7
const HANDLE_HIT_MIN = 22
const RANGE_HANDLE = 7
const RANGE_EDGE_HIT = 10
const TOOLBAR_GAP = 14
const TOOLBAR_EST_W = 260
const TOOLBAR_EST_H = 140

const diagramStore = useDiagramSession()
const { t } = useLanguage()
const { getNodes, viewport: vueFlowViewport, getViewport } = useVueFlow(diagramStore.vueFlowId)

const HOVER_LEAVE_MS = 160

const overlayRoot = ref<HTMLElement | null>(null)
const toolbarSummaryId = ref<string | null>(null)
const hoveredSummaryId = ref<string | null>(null)
const rangeDrag = ref<SummaryRangeDrag | null>(null)
let hoverLeaveTimer: ReturnType<typeof setTimeout> | null = null

const viewport = computed(() => vueFlowViewport.value ?? getViewport())

const isV2MindMap = computed(() => {
  const type = diagramStore.type
  if (type !== 'mindmap' && type !== 'mind_map') return false
  return isSessionMindMapV2VisualDesignActive(diagramStore.mindMapCanvasMode)
})

const summaries = computed(() => (isV2MindMap.value ? readMindMapSummaries(diagramStore.data) : []))

const themeStroke = computed(() => {
  const theme = getMindMapThemeForDiagram(diagramStore.data)
  return theme.borderColor || '#c2410c'
})

type BraceElement = {
  id: string
  bracePath: string
  connectorPath: string
  handleX: number
  handleY: number
  rangeX: number
  rangeY: number
  rangeW: number
  rangeH: number
  selected: boolean
  stroke: string
  strokeWidth: number
  dasharray: string | undefined
}

const elements = computed<BraceElement[]>(() => {
  const data = diagramStore.data
  if (!isV2MindMap.value || !data?.nodes) return []
  const widths = diagramStore.mindMapNodeWidths ?? {}
  const heights = diagramStore.mindMapNodeHeights ?? {}
  const connections = data.connections ?? []
  const selectedId = toolbarSummaryId.value
  const out: BraceElement[] = []

  const drag = rangeDrag.value
  for (const summary of summaries.value) {
    const boxes = coveredBoxesForSummary(data.nodes, connections, summary, widths, heights)
    if (boxes.length === 0) continue
    const side = summary.coveredPaths[0]?.startsWith('l/') ? 'left' : 'right'
    const kind = resolveMindMapSummaryKind(summary)
    let layoutBoxes = boxes
    let rangeOverride: { x: number; y: number; width: number; height: number } | undefined
    if (drag && drag.summaryId === summary.id) {
      const slots = siblingBoxesForSummary(data.nodes, connections, summary, widths, heights)
      const previewBoxes = slots
        .filter((slot) => drag.previewPaths.includes(slot.path))
        .map((slot) => ({
          x: slot.x,
          y: slot.y,
          width: slot.width,
          height: slot.height,
        }))
      if (previewBoxes.length > 0) layoutBoxes = previewBoxes
      const padded = mindMapSummaryPaddedRangeRect(layoutBoxes)
      if (padded) {
        rangeOverride = { ...padded, y: drag.previewY, height: drag.previewH }
      }
    }
    const brace = mindMapSummaryBracePath(layoutBoxes, side, { kind, rangeRect: rangeOverride })
    if (!brace) continue
    const rootId = mindMapSummaryRootNodeId(summary.id)
    const vf = getNodes.value.find((node) => node.id === rootId)
    const summaryBox = vf
      ? {
          x: vf.position.x,
          y: vf.position.y,
          width: vf.dimensions?.width ?? widths[rootId] ?? 90,
          height: vf.dimensions?.height ?? heights[rootId] ?? 34,
        }
      : null
    const connector = summaryBox
      ? mindMapSummaryConnectorPath(brace.tipX, brace.tipY, summaryBox, side)
      : ''
    const lineStyle = resolveMindMapSummaryLineStyle(summary)
    const strokeWidth = resolveMindMapSummaryStrokeWidth(summary)
    out.push({
      id: summary.id,
      bracePath: brace.bracePath,
      connectorPath: connector,
      handleX: brace.handleX,
      handleY: brace.handleY,
      rangeX: brace.rangeRect.x,
      rangeY: brace.rangeRect.y,
      rangeW: brace.rangeRect.width,
      rangeH: brace.rangeRect.height,
      selected: selectedId === summary.id || drag?.summaryId === summary.id,
      stroke: summary.strokeColor ?? themeStroke.value,
      strokeWidth,
      dasharray: mindMapSummaryStrokeDasharray(lineStyle, strokeWidth),
    })
  }
  return out
})

const toolbarAnchor = computed(() => {
  const summaryId = toolbarSummaryId.value
  const el = elements.value.find((item) => item.id === summaryId)
  const root = overlayRoot.value
  if (!summaryId || !el || !root) return null
  const pane = root.getBoundingClientRect()
  const vp = viewport.value
  const handleX = pane.left + vp.x + el.handleX * vp.zoom
  const handleY = pane.top + vp.y + el.handleY * vp.zoom
  const hit = Math.max(HANDLE_HIT_MIN, HANDLE_R * 2 * vp.zoom)
  let left = handleX + hit / 2 + TOOLBAR_GAP
  let top = handleY - 12
  if (left + TOOLBAR_EST_W > window.innerWidth - 8) {
    left = handleX - hit / 2 - TOOLBAR_GAP - TOOLBAR_EST_W
  }
  left = Math.min(Math.max(8, left), window.innerWidth - TOOLBAR_EST_W - 8)
  top = Math.min(Math.max(8, top), window.innerHeight - TOOLBAR_EST_H - 8)
  return { id: summaryId, left, top }
})

function handleButtonStyle(el: BraceElement): Record<string, string> {
  const vp = viewport.value
  const visual = Math.max(14, HANDLE_R * 2 * vp.zoom)
  const hit = Math.max(HANDLE_HIT_MIN, visual)
  return {
    left: `${vp.x + el.handleX * vp.zoom}px`,
    top: `${vp.y + el.handleY * vp.zoom}px`,
    width: `${hit}px`,
    height: `${hit}px`,
    '--mm-summary-disk': `${visual}px`,
    '--mm-summary-stroke': el.stroke,
  }
}

function showHandle(summaryId: string): boolean {
  return (
    toolbarSummaryId.value === summaryId ||
    hoveredSummaryId.value === summaryId ||
    rangeDrag.value?.summaryId === summaryId
  )
}

function setHoveredSummary(summaryId: string | null): void {
  if (hoverLeaveTimer !== null) {
    clearTimeout(hoverLeaveTimer)
    hoverLeaveTimer = null
  }
  if (summaryId) {
    hoveredSummaryId.value = summaryId
    return
  }
  hoverLeaveTimer = setTimeout(() => {
    hoveredSummaryId.value = null
    hoverLeaveTimer = null
  }, HOVER_LEAVE_MS)
}

const { onRangeEdgeDown, onRangeEdgeMove, onRangeEdgeUp, clearRangeDrag } =
  useMindMapSummaryRangeDrag({
    rangeDrag,
    overlayRoot,
    viewport,
    findRange: (summaryId) => {
      const el = elements.value.find((item) => item.id === summaryId)
      return el ? { rangeY: el.rangeY, rangeH: el.rangeH } : null
    },
    findSummary: (summaryId) => summaries.value.find((item) => item.id === summaryId),
  })

function deleteSummary(summaryId: string): void {
  toolbarSummaryId.value = null
  clearRangeDrag()
  diagramStore.removeMindMapNodes([mindMapSummaryRootNodeId(summaryId)])
}

function openToolbar(summaryId: string, event: MouseEvent): void {
  event.stopPropagation()
  event.preventDefault()
  if (toolbarSummaryId.value === summaryId) {
    closeToolbar()
    return
  }
  toolbarSummaryId.value = summaryId
  diagramStore.clearSelection()
}

function closeToolbar(): void {
  toolbarSummaryId.value = null
}

function isToolbarEvent(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false
  return Boolean(
    target.closest('.mm-summary-toolbar') ||
    target.closest('.mm-summary-toolbar-popper') ||
    target.closest('.mm-summary-handle-btn')
  )
}

function onDocumentPointerDown(event: PointerEvent): void {
  if (!toolbarSummaryId.value) return
  if (isToolbarEvent(event.target)) return
  closeToolbar()
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && toolbarSummaryId.value) {
    closeToolbar()
  }
}

watch(
  () => diagramStore.selectedNodes.slice(),
  (ids) => {
    if (toolbarSummaryId.value && ids.length > 0) {
      closeToolbar()
    }
  }
)

watch(summaries, (list) => {
  const open = toolbarSummaryId.value
  if (open && !list.some((item) => item.id === open)) {
    closeToolbar()
  }
})

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown, true)
  document.addEventListener('keydown', onDocumentKeydown)
})

onUnmounted(() => {
  if (hoverLeaveTimer !== null) {
    clearTimeout(hoverLeaveTimer)
    hoverLeaveTimer = null
  }
  document.removeEventListener('pointerdown', onDocumentPointerDown, true)
  document.removeEventListener('keydown', onDocumentKeydown)
})
</script>

<template>
  <div
    v-if="elements.length > 0"
    ref="overlayRoot"
    class="mm-summary-overlay"
  >
    <svg
      class="mm-summary-overlay__svg"
      aria-hidden="true"
    >
      <g :transform="`translate(${viewport.x}, ${viewport.y}) scale(${viewport.zoom})`">
        <g
          v-for="el in elements"
          :key="el.id"
          class="mm-summary-chrome"
          :class="{ 'is-selected': el.selected }"
        >
          <rect
            class="mm-summary-range"
            :x="el.rangeX"
            :y="el.rangeY"
            :width="el.rangeW"
            :height="el.rangeH"
            pointer-events="none"
            :fill="el.selected ? 'rgba(37, 99, 235, 0.08)' : 'transparent'"
            :stroke="el.selected ? '#2563eb' : el.stroke"
            :stroke-width="Math.max(1, el.strokeWidth * (el.selected ? 0.9 : 0.65))"
            :stroke-dasharray="el.dasharray"
          />
          <rect
            class="mm-summary-range-edge"
            :x="el.rangeX"
            :y="el.rangeY - RANGE_EDGE_HIT / 2"
            :width="el.rangeW"
            :height="RANGE_EDGE_HIT"
            @pointerenter="setHoveredSummary(el.id)"
            @pointerleave="setHoveredSummary(null)"
            @pointerdown.stop.prevent="onRangeEdgeDown(el.id, 'top', $event)"
            @pointermove="onRangeEdgeMove"
            @pointerup="onRangeEdgeUp"
            @pointercancel="onRangeEdgeUp"
          />
          <rect
            class="mm-summary-range-edge"
            :x="el.rangeX"
            :y="el.rangeY + el.rangeH - RANGE_EDGE_HIT / 2"
            :width="el.rangeW"
            :height="RANGE_EDGE_HIT"
            @pointerenter="setHoveredSummary(el.id)"
            @pointerleave="setHoveredSummary(null)"
            @pointerdown.stop.prevent="onRangeEdgeDown(el.id, 'bottom', $event)"
            @pointermove="onRangeEdgeMove"
            @pointerup="onRangeEdgeUp"
            @pointercancel="onRangeEdgeUp"
          />
          <rect
            class="mm-summary-range-grip"
            :x="el.rangeX + el.rangeW / 2 - RANGE_HANDLE / 2"
            :y="el.rangeY - RANGE_HANDLE / 2"
            :width="RANGE_HANDLE"
            :height="RANGE_HANDLE"
            :stroke="el.selected ? '#2563eb' : el.stroke"
            @pointerenter="setHoveredSummary(el.id)"
            @pointerleave="setHoveredSummary(null)"
            @pointerdown.stop.prevent="onRangeEdgeDown(el.id, 'top', $event)"
            @pointermove="onRangeEdgeMove"
            @pointerup="onRangeEdgeUp"
            @pointercancel="onRangeEdgeUp"
          />
          <rect
            class="mm-summary-range-grip"
            :x="el.rangeX + el.rangeW / 2 - RANGE_HANDLE / 2"
            :y="el.rangeY + el.rangeH - RANGE_HANDLE / 2"
            :width="RANGE_HANDLE"
            :height="RANGE_HANDLE"
            :stroke="el.selected ? '#2563eb' : el.stroke"
            @pointerenter="setHoveredSummary(el.id)"
            @pointerleave="setHoveredSummary(null)"
            @pointerdown.stop.prevent="onRangeEdgeDown(el.id, 'bottom', $event)"
            @pointermove="onRangeEdgeMove"
            @pointerup="onRangeEdgeUp"
            @pointercancel="onRangeEdgeUp"
          />
          <path
            class="mm-summary-hit"
            :d="el.bracePath"
            fill="none"
            stroke="transparent"
            stroke-width="16"
            pointer-events="stroke"
            @pointerenter="setHoveredSummary(el.id)"
            @pointerleave="setHoveredSummary(null)"
          />
          <path
            v-if="el.connectorPath"
            class="mm-summary-hit"
            :d="el.connectorPath"
            fill="none"
            stroke="transparent"
            stroke-width="16"
            pointer-events="stroke"
            @pointerenter="setHoveredSummary(el.id)"
            @pointerleave="setHoveredSummary(null)"
          />
          <path
            :d="el.bracePath"
            fill="none"
            :stroke="el.selected ? '#2563eb' : el.stroke"
            :stroke-width="el.selected ? el.strokeWidth + 0.75 : el.strokeWidth"
            stroke-linecap="round"
            stroke-linejoin="round"
            :stroke-dasharray="el.dasharray"
          />
          <path
            v-if="el.connectorPath"
            :d="el.connectorPath"
            fill="none"
            :stroke="el.selected ? '#2563eb' : el.stroke"
            :stroke-width="el.selected ? el.strokeWidth + 0.75 : el.strokeWidth"
            stroke-linecap="round"
            :stroke-dasharray="el.dasharray"
          />
        </g>
      </g>
    </svg>
    <button
      v-for="el in elements"
      v-show="showHandle(el.id)"
      :key="`handle-${el.id}`"
      type="button"
      class="mm-summary-handle-btn"
      :class="{ 'is-selected': el.selected }"
      :style="handleButtonStyle(el)"
      :title="t('canvas.floatingToolbar.summaryStyle')"
      :aria-label="t('canvas.floatingToolbar.summaryStyle')"
      @pointerenter="setHoveredSummary(el.id)"
      @pointerleave="setHoveredSummary(null)"
      @pointerdown.stop.prevent="openToolbar(el.id, $event)"
      @dblclick.stop.prevent="deleteSummary(el.id)"
    >
      <span class="mm-summary-handle-btn__disk" />
      <span class="mm-summary-handle-btn__dots">
        <span />
        <span />
        <span />
      </span>
    </button>
    <MindMapSummaryFloatingToolbar
      v-if="toolbarAnchor"
      :summary-id="toolbarAnchor.id"
      :left="toolbarAnchor.left"
      :top="toolbarAnchor.top"
      :theme-stroke="themeStroke"
    />
  </div>
</template>

<style scoped>
.mm-summary-overlay {
  position: absolute;
  inset: 0;
  overflow: visible;
  pointer-events: none;
  z-index: 4502;
}

.mm-summary-overlay__svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.mm-summary-chrome {
  pointer-events: none;
}

.mm-summary-range-edge {
  fill: transparent;
  cursor: ns-resize;
  pointer-events: all;
}

.mm-summary-range-grip {
  fill: #fff;
  stroke-width: 1.25;
  cursor: ns-resize;
  pointer-events: all;
}

.mm-summary-hit {
  pointer-events: stroke;
}

.mm-summary-handle-btn {
  position: absolute;
  transform: translate(-50%, -50%);
  padding: 0;
  border: none;
  background: transparent;
  pointer-events: auto;
  cursor: pointer;
  z-index: 1;
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
</style>
