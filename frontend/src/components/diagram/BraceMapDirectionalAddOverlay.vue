<script setup lang="ts">
/**
 * Contextual + handles for brace maps (Teleport).
 * The whole grows a part to the right. Every other node inserts a sibling
 * above or below, and grows the next level to the right.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useBraceMapAddPosition, useCanvasNodeChromeOverlayGate } from '@/composables/canvasToolbar'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { createThinkingMapLevelAdds } from '@/composables/editor/thinkingMapLevelAdd'
import { isDragPracticeDiagramLocked } from '@/composables/mindMap/dragPracticeMode'
import { learningSheetPickActive } from '@/composables/mindMap/useLearningSheetCustomMode'
import { effectiveCanvasInputMode } from '@/config/canvasInputMode'
import { mindMapControlScale } from '@/config/mindMapEBlackboard'
import { diagramInsertLabel } from '@/diagramBilingual/insertLabel'
import { useUIStore } from '@/stores/ui'
import {
  type BraceMapAddAction,
  braceChildIds,
  braceParentId,
  resolveBraceMapAddSelectionKind,
} from '@/utils/braceMapAddHandles'
import { findBraceMapWholeId, isBraceMapWholeNode } from '@/utils/braceMapIdentity'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'
import { isMobileRoutePath } from '@/utils/mobileRouteRedirect'

const props = defineProps<{
  containerRef: HTMLElement | null
  teleportTarget?: HTMLElement | string
  /** Presentation / readonly lock from DiagramCanvas. */
  editLocked?: boolean
}>()

const diagramStore = useDiagramSession()
const uiStore = useUIStore()
const route = useRoute()
const { t } = useLanguage()
const notify = useNotifications()
const overlayBlocksNodeChrome = useCanvasNodeChromeOverlayGate()

const label = (key: string, named?: Record<string, unknown>) =>
  diagramInsertLabel(diagramStore.data?.languages, key, named)
const { addBraceNextLevelNode } = createThinkingMapLevelAdds(
  diagramStore,
  (key, named) => (named ? t(key, named) : t(key)),
  label,
  notify
)

const controlScale = computed(() =>
  mindMapControlScale(
    effectiveCanvasInputMode(uiStore.canvasInputMode, isMobileRoutePath(route.path))
  )
)
const overlayStyle = computed(() => ({
  '--brace-eb-scale': String(controlScale.value),
}))

const editingNodeId = ref<string | null>(null)
const isBraceMap = computed(() => diagramStore.type === 'brace_map')

const selectedNodeId = computed(() => {
  const ids = diagramStore.selectedNodes
  return isBraceMap.value && ids.length === 1 ? ids[0] : null
})

const selectedNode = computed(() => {
  const id = selectedNodeId.value
  if (!id) return null
  return diagramStore.data?.nodes?.find((node) => node.id === id) ?? null
})

const selectionKind = computed(() =>
  selectedNode.value ? resolveBraceMapAddSelectionKind(selectedNode.value) : null
)

const overlayEnabled = computed(
  () =>
    isBraceMap.value &&
    !!selectedNodeId.value &&
    !!selectionKind.value &&
    editingNodeId.value !== selectedNodeId.value &&
    !props.editLocked &&
    !learningSheetPickActive.value &&
    !isDragPracticeDiagramLocked() &&
    !overlayBlocksNodeChrome.value &&
    !uiStore.exportWireframeOutline &&
    !isMindgraphHeadlessExportSession()
)

const containerRef = computed(() => props.containerRef)

const { handles, visible, scheduleMeasure } = useBraceMapAddPosition({
  containerRef,
  selectedNodeId,
  selectionKind,
  enabled: overlayEnabled,
  controlScale,
})

watch(
  () => diagramStore.data?.nodes?.map((n) => `${n.id}:${n.position?.x}:${n.position?.y}`).join('|'),
  () => scheduleMeasure()
)

function parentOf(nodeId: string) {
  const parentId = braceParentId(nodeId, diagramStore.data?.connections ?? [])
  if (!parentId) return null
  return diagramStore.data?.nodes?.find((item) => item.id === parentId) ?? null
}

function tooltipFor(action: BraceMapAddAction): string {
  if (action === 'child-append') {
    const key =
      selectionKind.value === 'whole' ? 'canvas.toolbar.addPart' : 'canvas.toolbar.addNextLevel'
    return t(key)
  }
  const nodeId = selectedNode.value?.id
  const parent = nodeId ? parentOf(nodeId) : null
  const key =
    parent && isBraceMapWholeNode(parent) ? 'canvas.toolbar.addPart' : 'canvas.toolbar.addSubpart'
  return t(key)
}

function selectById(nodeId: string | undefined): void {
  if (nodeId) diagramStore.selectNodes(nodeId)
}

function insertSibling(nodeId: string, atIndex: number): boolean {
  const connections = diagramStore.data?.connections ?? []
  const parentId = braceParentId(nodeId, connections)
  if (!parentId) return false
  const nodes = diagramStore.data?.nodes ?? []
  const parent = nodes.find((node) => node.id === parentId)
  const underWhole = parent ? isBraceMapWholeNode(parent) : false
  const id = diagramStore.insertBraceMapChild(
    parentId,
    label(underWhole ? 'canvas.toolbar.newPart' : 'canvas.toolbar.newSubpart'),
    atIndex
  )
  if (!id) return false
  selectById(id)
  notify.successKey(underWhole ? 'canvas.toolbar.partAdded' : 'canvas.toolbar.subpartAdded')
  return true
}

function handleClick(action: BraceMapAddAction, event: MouseEvent): void {
  event.stopPropagation()
  event.preventDefault()
  const node = selectedNode.value
  if (!node?.id) return
  const connections = diagramStore.data?.connections ?? []

  if (action === 'child-append') {
    if (selectionKind.value === 'whole') {
      const wholeId = findBraceMapWholeId(diagramStore.data?.nodes ?? [], connections) ?? node.id
      const id = diagramStore.insertBraceMapChild(
        wholeId,
        label('canvas.toolbar.newPart'),
        braceChildIds(wholeId, connections).length
      )
      if (!id) return
      selectById(id)
      notify.successKey('canvas.toolbar.partAdded')
      return
    }
    addBraceNextLevelNode()
    return
  }

  const parentId = braceParentId(node.id, connections)
  const siblings = parentId ? braceChildIds(parentId, connections) : []
  const index = siblings.indexOf(node.id)
  const at = index < 0 ? siblings.length : index
  insertSibling(node.id, action === 'sibling-before' ? at : at + 1)
}

let unsubOpen: (() => void) | undefined
let unsubClose: (() => void) | undefined
let unsubZoom: (() => void) | undefined
let unsubFit: (() => void) | undefined
let unsubNodeAdded: (() => void) | undefined
let followupMeasureTimers: number[] = []

function scheduleFollowupMeasure(): void {
  scheduleMeasure()
  for (const timer of followupMeasureTimers) window.clearTimeout(timer)
  followupMeasureTimers = [80, 200].map((delay) => window.setTimeout(scheduleMeasure, delay))
}

onMounted(() => {
  unsubOpen = eventBus.on('node_editor:opening', ({ nodeId }) => {
    editingNodeId.value = nodeId
  })
  unsubClose = eventBus.on('node_editor:closed', ({ nodeId }) => {
    if (editingNodeId.value === nodeId) editingNodeId.value = null
    scheduleMeasure()
  })
  unsubZoom = diagramStore.viewBus.on('view:zoom_changed', scheduleMeasure)
  unsubFit = diagramStore.viewBus.on('view:fit_completed', scheduleMeasure)
  unsubNodeAdded = eventBus.on('diagram:node_added', scheduleFollowupMeasure)
  window.addEventListener('scroll', scheduleMeasure, true)
  window.addEventListener('resize', scheduleMeasure)
})

onUnmounted(() => {
  unsubOpen?.()
  unsubClose?.()
  unsubZoom?.()
  unsubFit?.()
  unsubNodeAdded?.()
  for (const timer of followupMeasureTimers) window.clearTimeout(timer)
  followupMeasureTimers = []
  window.removeEventListener('scroll', scheduleMeasure, true)
  window.removeEventListener('resize', scheduleMeasure)
})
</script>

<template>
  <Teleport :to="props.teleportTarget ?? 'body'">
    <div
      v-if="visible && overlayEnabled && handles.length"
      class="brace-map-add-overlay"
      :style="overlayStyle"
      aria-hidden="false"
    >
      <button
        v-for="handle in handles"
        :key="`${handle.action}-${handle.left}-${handle.top}`"
        type="button"
        class="brace-map-add-overlay__btn"
        :style="{ left: `${handle.left}px`, top: `${handle.top}px` }"
        :title="tooltipFor(handle.action)"
        :aria-label="tooltipFor(handle.action)"
        @click="handleClick(handle.action, $event)"
        @mousedown.stop
        @pointerdown.stop
      >
        +
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.brace-map-add-overlay {
  --brace-eb-scale: 1;
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 4500;
}

.brace-map-add-overlay__btn {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(16px * var(--brace-eb-scale));
  height: calc(16px * var(--brace-eb-scale));
  margin: 0;
  padding: 0;
  border: 1px solid #cbd5e1;
  border-radius: 50%;
  background: #fff;
  color: #64748b;
  font-size: calc(12px * var(--brace-eb-scale));
  font-weight: 500;
  line-height: 1;
  cursor: pointer;
  pointer-events: auto;
  transform: translate(-50%, -50%);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
  transition:
    transform 0.15s ease,
    background 0.15s ease,
    border-color 0.15s ease;
}

.brace-map-add-overlay__btn:hover {
  transform: translate(-50%, -50%) scale(1.08);
  background: #e2e8f0;
  border-color: #94a3b8;
  color: #475569;
}
</style>
