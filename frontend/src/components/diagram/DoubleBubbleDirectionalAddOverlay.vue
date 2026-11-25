<script setup lang="ts">
/**
 * Contextual + handles for double-bubble maps (Teleport).
 * Similarity / difference adds reuse thinking-map level helpers.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useLanguage } from '@/composables'
import {
  useCanvasNodeChromeOverlayGate,
  useDoubleBubbleAddPosition,
} from '@/composables/canvasToolbar'
import { eventBus } from '@/composables/core/useEventBus'
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
  type DoubleBubbleAddAction,
  resolveDoubleBubbleAddSelectionKind,
} from '@/utils/doubleBubbleAddHandles'
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
const { addDoubleBubbleSimilarityNode, addDoubleBubbleDifferenceNode } = createThinkingMapLevelAdds(
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
  '--db-eb-scale': String(controlScale.value),
}))

const editingNodeId = ref<string | null>(null)
const isDoubleBubble = computed(() => diagramStore.type === 'double_bubble_map')

const selectedNodeId = computed(() => {
  const ids = diagramStore.selectedNodes
  return isDoubleBubble.value && ids.length === 1 ? ids[0] : null
})

const selectedNode = computed(() => {
  const id = selectedNodeId.value
  if (!id) return null
  return diagramStore.data?.nodes?.find((node) => node.id === id) ?? null
})

const selectionKind = computed(() =>
  selectedNode.value ? resolveDoubleBubbleAddSelectionKind(selectedNode.value) : null
)

const overlayEnabled = computed(
  () =>
    isDoubleBubble.value &&
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

const { handles, visible, scheduleMeasure } = useDoubleBubbleAddPosition({
  containerRef,
  selectedNodeId,
  selectionKind,
  enabled: overlayEnabled,
  controlScale,
})

watch(
  () =>
    diagramStore.data?.nodes
      ?.map((n) => `${n.id}:${n.position?.x}:${n.position?.y}:${n.data?.groupIndex ?? ''}`)
      .join('|'),
  () => scheduleMeasure()
)

function tooltipFor(action: DoubleBubbleAddAction): string {
  return action === 'similarity'
    ? t('canvas.doubleBubble.addSimilarity')
    : t('canvas.doubleBubble.addDifference')
}

function handleClick(action: DoubleBubbleAddAction, event: MouseEvent): void {
  event.stopPropagation()
  event.preventDefault()
  if (action === 'similarity') {
    addDoubleBubbleSimilarityNode()
    return
  }
  addDoubleBubbleDifferenceNode()
}

let unsubOpen: (() => void) | undefined
let unsubClose: (() => void) | undefined
let unsubZoom: (() => void) | undefined
let unsubFit: (() => void) | undefined

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
  eventBus.on('diagram:node_added', () => {
    scheduleMeasure()
    setTimeout(scheduleMeasure, 80)
    setTimeout(scheduleMeasure, 200)
  })
  window.addEventListener('scroll', scheduleMeasure, true)
  window.addEventListener('resize', scheduleMeasure)
})

onUnmounted(() => {
  unsubOpen?.()
  unsubClose?.()
  unsubZoom?.()
  unsubFit?.()
  window.removeEventListener('scroll', scheduleMeasure, true)
  window.removeEventListener('resize', scheduleMeasure)
})
</script>

<template>
  <Teleport :to="props.teleportTarget ?? 'body'">
    <div
      v-if="visible && overlayEnabled && handles.length"
      class="double-bubble-add-overlay"
      :style="overlayStyle"
      aria-hidden="false"
    >
      <button
        v-for="handle in handles"
        :key="`${handle.action}-${handle.left}-${handle.top}`"
        type="button"
        class="double-bubble-add-overlay__btn"
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
.double-bubble-add-overlay {
  --db-eb-scale: 1;
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 4500;
}

.double-bubble-add-overlay__btn {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(16px * var(--db-eb-scale));
  height: calc(16px * var(--db-eb-scale));
  margin: 0;
  padding: 0;
  border: 1px solid #cbd5e1;
  border-radius: 50%;
  background: #fff;
  color: #64748b;
  font-size: calc(12px * var(--db-eb-scale));
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

.double-bubble-add-overlay__btn:hover {
  transform: translate(-50%, -50%) scale(1.08);
  background: #e2e8f0;
  border-color: #94a3b8;
  color: #475569;
}
</style>
