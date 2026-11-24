<script setup lang="ts">
/**
 * Contextual + handles for tree maps (Teleport).
 * Topic/category/leaf sides insert categories or leaves at the chosen index.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useCanvasNodeChromeOverlayGate, useTreeMapAddPosition } from '@/composables/canvasToolbar'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { dragPracticePicking } from '@/composables/mindMap/useDragPractice'
import { learningSheetPickActive } from '@/composables/mindMap/useLearningSheetCustomMode'
import { effectiveCanvasInputMode } from '@/config/canvasInputMode'
import { mindMapControlScale } from '@/config/mindMapEBlackboard'
import { diagramInsertLabel } from '@/diagramBilingual/insertLabel'
import { useUIStore } from '@/stores/ui'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'
import { isMobileRoutePath } from '@/utils/mobileRouteRedirect'
import { type TreeMapAddAction, resolveTreeMapAddSelectionKind } from '@/utils/treeMapAddHandles'
import {
  TREE_TOPIC_NODE_ID,
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
  readTreeCategoryIndex,
  readTreeLeafIndex,
  readTreeParentCategoryId,
  treeMapColumnsOf,
} from '@/utils/treeMapIdentity'

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

const controlScale = computed(() =>
  mindMapControlScale(
    effectiveCanvasInputMode(uiStore.canvasInputMode, isMobileRoutePath(route.path))
  )
)
const overlayStyle = computed(() => ({
  '--tree-eb-scale': String(controlScale.value),
}))

const editingNodeId = ref<string | null>(null)
const isTreeMap = computed(() => diagramStore.type === 'tree_map')

const selectedNodeId = computed(() => {
  const ids = diagramStore.selectedNodes
  return isTreeMap.value && ids.length === 1 ? ids[0] : null
})

const selectedNode = computed(() => {
  const id = selectedNodeId.value
  if (!id) return null
  return diagramStore.data?.nodes?.find((node) => node.id === id) ?? null
})

const selectionKind = computed(() =>
  selectedNode.value ? resolveTreeMapAddSelectionKind(selectedNode.value) : null
)

const overlayEnabled = computed(
  () =>
    isTreeMap.value &&
    !!selectedNodeId.value &&
    !!selectionKind.value &&
    editingNodeId.value !== selectedNodeId.value &&
    !props.editLocked &&
    !learningSheetPickActive.value &&
    !dragPracticePicking.value &&
    !overlayBlocksNodeChrome.value &&
    !uiStore.exportWireframeOutline &&
    !isMindgraphHeadlessExportSession()
)

const containerRef = computed(() => props.containerRef)

const { handles, visible, scheduleMeasure } = useTreeMapAddPosition({
  containerRef,
  selectedNodeId,
  selectionKind,
  enabled: overlayEnabled,
  controlScale,
})

watch(
  () =>
    diagramStore.data?.nodes
      ?.map(
        (n) =>
          `${n.id}:${n.position?.x}:${n.position?.y}:${n.data?.categoryIndex ?? ''}:${n.data?.leafIndex ?? ''}`
      )
      .join('|'),
  () => scheduleMeasure()
)

function tooltipFor(action: TreeMapAddAction): string {
  if (action === 'category-before' || action === 'category-after') {
    return t('canvas.toolbar.addBranch')
  }
  return t('canvas.toolbar.addTreeItem')
}

function selectById(nodeId: string | undefined): void {
  if (nodeId) diagramStore.selectNodes(nodeId)
}

function addCategoryAt(atIndex: number): boolean {
  if (!diagramStore.insertTreeMapCategory(label('diagram.newCategory'), atIndex)) return false
  const columns = treeMapColumnsOf(diagramStore.data?.nodes ?? [])
  selectById(columns[Math.min(atIndex, columns.length - 1)]?.category.id)
  notify.successKey('canvas.toolbar.branchAdded')
  return true
}

function addLeafAt(categoryId: string, atIndex: number | undefined): boolean {
  const nodes = diagramStore.data?.nodes ?? []
  const column = treeMapColumnsOf(nodes).find((entry) => entry.category.id === categoryId)
  const index = atIndex === undefined ? (column?.leaves.length ?? 0) : atIndex
  if (!diagramStore.insertTreeMapChild(categoryId, label('diagram.newItem'), index)) {
    return false
  }
  const refreshed = treeMapColumnsOf(diagramStore.data?.nodes ?? []).find(
    (entry) => entry.category.id === categoryId
  )
  const leaves = refreshed?.leaves ?? []
  const pick =
    atIndex === undefined ? leaves[leaves.length - 1] : leaves[Math.min(atIndex, leaves.length - 1)]
  selectById(pick?.id)
  notify.successKey('canvas.toolbar.childAdded')
  return true
}

function handleClick(action: TreeMapAddAction, event: MouseEvent): void {
  event.stopPropagation()
  event.preventDefault()
  const node = selectedNode.value
  const nodes = diagramStore.data?.nodes ?? []
  if (!node) return

  if (action === 'category-after' || action === 'category-before') {
    const kind = resolveTreeMapAddSelectionKind(node)
    if (kind === 'topic' || node.id === TREE_TOPIC_NODE_ID) {
      addCategoryAt(treeMapColumnsOf(nodes).length)
      return
    }
    const columns = treeMapColumnsOf(nodes)
    const idx = columns.findIndex((column) => column.category.id === node.id)
    if (idx < 0) {
      addCategoryAt(columns.length)
      return
    }
    addCategoryAt(action === 'category-before' ? idx : idx + 1)
    return
  }

  if (action === 'leaf-append') {
    if (!isTreeMapCategoryNode(node) || !node.id) return
    addLeafAt(node.id, undefined)
    return
  }

  if (!isTreeMapLeafNode(node) || !node.id) return
  const categoryId =
    readTreeParentCategoryId(node) ??
    treeMapColumnsOf(nodes).find(
      (column) => readTreeCategoryIndex(column.category) === readTreeCategoryIndex(node)
    )?.category.id
  if (!categoryId) return
  const siblings =
    treeMapColumnsOf(nodes).find((column) => column.category.id === categoryId)?.leaves ?? []
  const currentIdx = siblings.findIndex((item) => item.id === node.id)
  const stamped = readTreeLeafIndex(node)
  const index = currentIdx >= 0 ? currentIdx : stamped >= 0 ? stamped : siblings.length
  addLeafAt(categoryId, action === 'leaf-before' ? index : index + 1)
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
      class="tree-map-add-overlay"
      :style="overlayStyle"
      aria-hidden="false"
    >
      <button
        v-for="handle in handles"
        :key="`${handle.action}-${handle.left}-${handle.top}`"
        type="button"
        class="tree-map-add-overlay__btn"
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
.tree-map-add-overlay {
  --tree-eb-scale: 1;
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 4500;
}

.tree-map-add-overlay__btn {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(16px * var(--tree-eb-scale));
  height: calc(16px * var(--tree-eb-scale));
  margin: 0;
  padding: 0;
  border: 1px solid #cbd5e1;
  border-radius: 50%;
  background: #fff;
  color: #64748b;
  font-size: calc(12px * var(--tree-eb-scale));
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

.tree-map-add-overlay__btn:hover {
  transform: translate(-50%, -50%) scale(1.08);
  background: #e2e8f0;
  border-color: #94a3b8;
  color: #475569;
}
</style>
