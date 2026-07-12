<script setup lang="ts">
/**
 * Mind-map collapse (−) / expand (count pill) on the connector midpoint, with stub line when collapsed.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Teleport } from 'vue'

import { useLanguage } from '@/composables'
import { useMindMapCollapseOverlayPositions, resolveMindMapCollapseHoverNodeId, isMindMapCollapseEligibleNode } from '@/composables/canvasToolbar/useMindMapCollapseTogglePosition'
import { eventBus } from '@/composables/core/useEventBus'
import { MIND_MAP_GEOMETRY, resolveMindMapTopicBorderColor } from '@/config/mindMapGeometry'
import {
  isMindMapPathCollapsed,
  mindMapDescendantCount,
} from '@/stores/diagram/mindMapCollapse'
import { useDiagramStore } from '@/stores/diagram'

const props = defineProps<{
  containerRef: HTMLElement | null
  teleportTarget?: HTMLElement | string
}>()

const diagramStore = useDiagramStore()
const { t } = useLanguage()

const editingNodeId = ref<string | null>(null)
const hoveredNodeId = ref<string | null>(null)
const pinnedCollapseNodeId = ref<string | null>(null)

const activeCollapseNodeId = computed(
  () => hoveredNodeId.value ?? pinnedCollapseNodeId.value
)

let hoverClearTimer: ReturnType<typeof setTimeout> | null = null

function setHoveredNodeId(id: string | null, immediate = false): void {
  if (hoverClearTimer) {
    clearTimeout(hoverClearTimer)
    hoverClearTimer = null
  }
  if (id) {
    hoveredNodeId.value = id
    return
  }
  if (immediate) {
    hoveredNodeId.value = null
    return
  }
  hoverClearTimer = setTimeout(() => {
    hoveredNodeId.value = null
    hoverClearTimer = null
  }, 150)
}

function isCollapseOverlayTarget(target: EventTarget | null): boolean {
  return target instanceof Element && Boolean(target.closest('.mind-map-collapse-overlay'))
}

function onContainerMouseOver(event: MouseEvent): void {
  const id = resolveMindMapCollapseHoverNodeId(
    event.target,
    diagramStore.data?.connections
  )
  if (id) {
    setHoveredNodeId(id)
    return
  }
  setHoveredNodeId(null)
}

function onContainerClick(event: MouseEvent): void {
  if (isCollapseOverlayTarget(event.target)) return
  const id = resolveMindMapCollapseHoverNodeId(
    event.target,
    diagramStore.data?.connections
  )
  if (id && isMindMapCollapseEligibleNode(id, diagramStore.data?.connections)) {
    pinnedCollapseNodeId.value = id
    setHoveredNodeId(id)
    return
  }
  pinnedCollapseNodeId.value = null
}

function onContainerMouseLeave(event: MouseEvent): void {
  if (isCollapseOverlayTarget(event.relatedTarget)) return
  setHoveredNodeId(null)
}

function onCollapseButtonEnter(nodeId: string): void {
  setHoveredNodeId(nodeId)
}

function onCollapseButtonLeave(nodeId: string, event: PointerEvent): void {
  const related = event.relatedTarget
  if (related instanceof Element) {
    const relatedNodeId = related.closest('.vue-flow__node')?.getAttribute('data-id')
    if (relatedNodeId === nodeId) return
    if (related.closest('.mind-map-collapse-overlay__btn')) return
    const edgeParentId = resolveMindMapCollapseHoverNodeId(
      related,
      diagramStore.data?.connections
    )
    if (edgeParentId === nodeId) return
  }
  setHoveredNodeId(null)
}

const isMindMap = computed(
  () => diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
)

const overlayEnabled = computed(() => isMindMap.value)

const containerRef = computed(() => props.containerRef)
const collapsedPaths = computed(() => diagramStore.data?._collapsed_paths ?? [])
const nodes = computed(() => diagramStore.data?.nodes)
const connections = computed(() => diagramStore.data?.connections)
const nodeStyles = computed(() => diagramStore.data?._node_styles)

const strokeColor = computed(() =>
  resolveMindMapTopicBorderColor(nodes.value?.find((n) => n.id === 'topic'))
)

const nodeWidths = computed(() => diagramStore.mindMapNodeWidths ?? {})
const nodeHeights = computed(() => diagramStore.mindMapNodeHeights ?? {})
const diagramStyleId = computed(
  () => diagramStore.data?._mindmap_diagram_style as string | undefined
)

const { handles, visible, scheduleMeasure } = useMindMapCollapseOverlayPositions({
  containerRef,
  activeCollapseNodeId,
  collapsedPaths,
  nodes,
  connections,
  nodeWidths,
  nodeHeights,
  nodeStyles,
  diagramStyleId,
  strokeColor,
  enabled: overlayEnabled,
  editingNodeId,
  getDescendantCount: (nodeId) =>
    mindMapDescendantCount(nodeId, diagramStore.getMindMapDescendantIds),
  getDescendantIds: diagramStore.getMindMapDescendantIds,
})

const expandHandles = computed(() => handles.value.filter((h) => h.mode === 'expand'))

watch(
  () =>
    diagramStore.data?.nodes
      ?.map((n) => `${n.id}:${n.position?.x}:${n.position?.y}`)
      .join('|'),
  () => scheduleMeasure()
)

function tooltipFor(handle: { nodeId: string; mode: 'collapse' | 'expand'; count?: number }): string {
  if (handle.mode === 'expand') {
    return t('mindMap.collapse.expand', { count: handle.count ?? 0 })
  }
  return t('mindMap.collapse.collapse')
}

function isNodeCollapsed(nodeId: string): boolean {
  const data = diagramStore.data
  if (!data?.connections) return false
  return isMindMapPathCollapsed(nodeId, data.connections, data._collapsed_paths ?? [])
}

function handleClick(
  handle: { nodeId: string; mode: 'collapse' | 'expand' },
  event: MouseEvent
): void {
  event.stopPropagation()
  event.preventDefault()
  if (handle.mode === 'expand' && !isNodeCollapsed(handle.nodeId)) return
  if (handle.mode === 'collapse' && isNodeCollapsed(handle.nodeId)) return
  diagramStore.toggleMindMapCollapse(handle.nodeId)
  pinnedCollapseNodeId.value = null
  scheduleMeasure()
}

function lineEndX(handle: { nodeId: string; left: number; mode: 'collapse' | 'expand' }): number {
  const half = handle.mode === 'expand' ? 14 : 9
  return handle.nodeId.startsWith('branch-l-') ? handle.left + half : handle.left - half
}

function buttonStyle(handle: { strokeColor: string }): Record<string, string> {
  return {
    borderColor: handle.strokeColor,
    color: handle.strokeColor,
  }
}

let unsubOpen: (() => void) | undefined
let unsubClose: (() => void) | undefined
let unsubPaneClick: (() => void) | undefined
let containerHoverEl: HTMLElement | null = null

function bindContainerHoverListeners(el: HTMLElement | null): void {
  if (containerHoverEl === el) return
  if (containerHoverEl) {
    containerHoverEl.removeEventListener('mouseover', onContainerMouseOver)
    containerHoverEl.removeEventListener('mouseleave', onContainerMouseLeave)
    containerHoverEl.removeEventListener('click', onContainerClick)
  }
  containerHoverEl = el
  if (!el) return
  el.addEventListener('mouseover', onContainerMouseOver)
  el.addEventListener('mouseleave', onContainerMouseLeave)
  el.addEventListener('click', onContainerClick)
}

watch(containerRef, bindContainerHoverListeners, { immediate: true })

onMounted(() => {
  unsubOpen = eventBus.on('node_editor:opening', ({ nodeId }) => {
    editingNodeId.value = nodeId
  })
  unsubClose = eventBus.on('node_editor:closed', ({ nodeId }) => {
    if (editingNodeId.value === nodeId) editingNodeId.value = null
    scheduleMeasure()
  })
  eventBus.on('view:zoom_changed', scheduleMeasure)
  eventBus.on('view:fit_completed', scheduleMeasure)
  eventBus.on('diagram:operation_completed', scheduleMeasure)
  unsubPaneClick = eventBus.on('canvas:pane_clicked', () => {
    pinnedCollapseNodeId.value = null
    setHoveredNodeId(null, true)
  })
  window.addEventListener('scroll', scheduleMeasure, true)
  window.addEventListener('resize', scheduleMeasure)
})

onUnmounted(() => {
  unsubOpen?.()
  unsubClose?.()
  unsubPaneClick?.()
  bindContainerHoverListeners(null)
  if (hoverClearTimer) clearTimeout(hoverClearTimer)
  window.removeEventListener('scroll', scheduleMeasure, true)
  window.removeEventListener('resize', scheduleMeasure)
})
</script>

<template>
  <Teleport :to="props.teleportTarget ?? 'body'">
    <div
      v-if="visible && overlayEnabled && handles.length"
      class="mind-map-collapse-overlay"
      aria-hidden="false"
    >
      <svg
        v-if="expandHandles.length"
        class="mind-map-collapse-overlay__lines"
        aria-hidden="true"
      >
        <line
          v-for="handle in expandHandles"
          :key="`line-${handle.nodeId}`"
          :x1="handle.lineStart.left"
          :y1="handle.lineStart.top"
          :x2="lineEndX(handle)"
          :y2="handle.top"
          :stroke="handle.strokeColor"
          :stroke-width="MIND_MAP_GEOMETRY.edgeStrokeWidth"
          :stroke-opacity="MIND_MAP_GEOMETRY.edgeStrokeOpacity"
          stroke-linecap="round"
        />
      </svg>

      <button
        v-for="handle in handles"
        :key="`${handle.nodeId}-${handle.mode}`"
        type="button"
        class="mind-map-collapse-overlay__btn"
        :class="{
          'mind-map-collapse-overlay__btn--collapse': handle.mode === 'collapse',
          'mind-map-collapse-overlay__btn--expand': handle.mode === 'expand',
        }"
        :style="{ left: `${handle.left}px`, top: `${handle.top}px`, ...buttonStyle(handle) }"
        :title="tooltipFor(handle)"
        :aria-label="tooltipFor(handle)"
        @click="handleClick(handle, $event)"
        @pointerenter="onCollapseButtonEnter(handle.nodeId)"
        @pointerleave="onCollapseButtonLeave(handle.nodeId, $event)"
        @mousedown.stop
        @pointerdown.stop
      >
        <span v-if="handle.mode === 'collapse'" class="mind-map-collapse-overlay__minus">−</span>
        <span v-else>{{ handle.count }}</span>
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.mind-map-collapse-overlay {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 4501;
}

.mind-map-collapse-overlay__lines {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: visible;
}

.mind-map-collapse-overlay__btn {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 0;
  border: 1.5px solid;
  background: #fff;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  pointer-events: auto;
  transform: translate(-50%, -50%);
  box-shadow: none;
  transition:
    transform 0.15s ease,
    background 0.15s ease;
}

.mind-map-collapse-overlay__btn--collapse {
  width: 18px;
  height: 18px;
  border-radius: 50%;
}

.mind-map-collapse-overlay__minus {
  font-size: 14px;
  font-weight: 500;
  line-height: 1;
  margin-top: -1px;
}

.mind-map-collapse-overlay__btn--expand {
  min-width: 28px;
  height: 18px;
  padding: 0 6px;
  border-radius: 999px;
  font-size: 11px;
}

.mind-map-collapse-overlay__btn:hover {
  transform: translate(-50%, -50%) scale(1.06);
  background: #fff;
}
</style>
