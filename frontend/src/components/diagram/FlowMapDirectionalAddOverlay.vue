<script setup lang="ts">
/**
 * Contextual + handles for flow maps (Teleport).
 * Topic/step/substep sides insert predecessor, successor, or append substeps.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useCanvasNodeChromeOverlayGate, useFlowMapAddPosition } from '@/composables/canvasToolbar'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { isDragPracticeDiagramLocked } from '@/composables/mindMap/dragPracticeMode'
import { learningSheetPickActive } from '@/composables/mindMap/useLearningSheetCustomMode'
import { effectiveCanvasInputMode } from '@/config/canvasInputMode'
import { mindMapControlScale } from '@/config/mindMapEBlackboard'
import { diagramInsertLabel } from '@/diagramBilingual/insertLabel'
import {
  orderFlowStepNodes,
  resolveFlowMapOrientation,
  substepsForFlowStep,
} from '@/stores/specLoader/flowMapSubsteps'
import { useUIStore } from '@/stores/ui'
import { type FlowMapAddAction, resolveFlowMapAddSelectionKind } from '@/utils/flowMapAddHandles'
import {
  FLOW_TOPIC_NODE_ID,
  findFlowMapParentStep,
  readFlowStepIndex,
  readFlowSubstepIndex,
} from '@/utils/flowMapIdentity'
import { resolveFlowMapSubstepArrangement } from '@/utils/flowMapSubstepArrangement'
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

const controlScale = computed(() =>
  mindMapControlScale(
    effectiveCanvasInputMode(uiStore.canvasInputMode, isMobileRoutePath(route.path))
  )
)
const overlayStyle = computed(() => ({
  '--flow-eb-scale': String(controlScale.value),
}))

const editingNodeId = ref<string | null>(null)
const isFlowMap = computed(() => diagramStore.type === 'flow_map')

const selectedNodeId = computed(() => {
  const ids = diagramStore.selectedNodes
  return isFlowMap.value && ids.length === 1 ? ids[0] : null
})

const selectedNode = computed(() => {
  const id = selectedNodeId.value
  if (!id) return null
  return diagramStore.data?.nodes?.find((node) => node.id === id) ?? null
})

const selectionKind = computed(() =>
  selectedNode.value ? resolveFlowMapAddSelectionKind(selectedNode.value) : null
)

const orientation = computed<'horizontal' | 'vertical'>(() => {
  const nodes = diagramStore.data?.nodes ?? []
  const topic = nodes.find((n) => n.id === FLOW_TOPIC_NODE_ID)
  const steps = orderFlowStepNodes(nodes)
  return resolveFlowMapOrientation(topic, steps)
})

const substepArrangement = computed(() => {
  const nodes = diagramStore.data?.nodes ?? []
  const topic = nodes.find((n) => n.id === FLOW_TOPIC_NODE_ID)
  return resolveFlowMapSubstepArrangement(
    topic,
    diagramStore.data as Record<string, unknown> | null
  )
})

const overlayEnabled = computed(
  () =>
    isFlowMap.value &&
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

const { handles, visible, scheduleMeasure } = useFlowMapAddPosition({
  containerRef,
  selectedNodeId,
  selectionKind,
  orientation,
  substepArrangement,
  enabled: overlayEnabled,
  controlScale,
})

watch(
  () =>
    diagramStore.data?.nodes
      ?.map(
        (n) =>
          `${n.id}:${n.position?.x}:${n.position?.y}:${n.style?.width ?? ''}:${n.data?.stepIndex ?? ''}`
      )
      .join('|'),
  () => scheduleMeasure()
)

function tooltipFor(action: FlowMapAddAction): string {
  if (action === 'step-before' || action === 'step-after') return t('canvas.toolbar.addStep')
  return t('canvas.toolbar.addSubstep')
}

function selectById(nodeId: string | undefined): void {
  if (nodeId) diagramStore.selectNodes(nodeId)
}

function addStepAt(atIndex: number): boolean {
  if (!diagramStore.insertFlowMapStepAt(label('canvas.toolbar.newStep'), atIndex)) return false
  const ordered = orderFlowStepNodes(diagramStore.data?.nodes ?? [])
  selectById(ordered[Math.min(atIndex, ordered.length - 1)]?.id)
  notify.successKey('canvas.toolbar.stepAdded')
  return true
}

function addSubstepAt(
  stepNode: { id: string; text?: string },
  atIndex: number | undefined
): boolean {
  const stepIndex = readFlowStepIndex(stepNode)
  if (
    !diagramStore.insertFlowMapSubstepAt(
      stepNode.text ?? '',
      label('canvas.toolbar.newSubstep'),
      atIndex,
      stepIndex >= 0 ? stepIndex : undefined,
      stepNode.id
    )
  ) {
    return false
  }
  const refreshed = diagramStore.data?.nodes ?? []
  const parent = refreshed.find((node) => node.id === stepNode.id)
  const children = parent
    ? substepsForFlowStep(
        refreshed.filter((node) => node.type === 'flowSubstep'),
        parent
      )
    : []
  const pick =
    atIndex === undefined
      ? children[children.length - 1]
      : children[Math.min(atIndex, children.length - 1)]
  selectById(pick?.id)
  notify.successKey('canvas.toolbar.substepAdded')
  return true
}

function handleClick(action: FlowMapAddAction, event: MouseEvent): void {
  event.stopPropagation()
  event.preventDefault()
  const node = selectedNode.value
  const nodes = diagramStore.data?.nodes ?? []
  if (!node) return

  if (action === 'step-after' || action === 'step-before') {
    const kind = resolveFlowMapAddSelectionKind(node)
    if (kind === 'topic') {
      addStepAt(0)
      return
    }
    const steps = orderFlowStepNodes(nodes)
    const idx = steps.findIndex((step) => step.id === node.id)
    if (idx < 0) {
      addStepAt(steps.length)
      return
    }
    addStepAt(action === 'step-before' ? idx : idx + 1)
    return
  }

  if (action === 'substep-append') {
    const stepNode = findFlowMapParentStep(node, nodes) ?? node
    addSubstepAt(stepNode, undefined)
    return
  }

  const parent = findFlowMapParentStep(node, nodes)
  if (!parent) {
    notify.warningKey('canvas.toolbar.selectStepForSubstep')
    return
  }
  const siblings = substepsForFlowStep(
    nodes.filter((item) => item.type === 'flowSubstep'),
    parent
  )
  const currentIdx = siblings.findIndex((item) => item.id === node.id)
  const stamped = readFlowSubstepIndex(node)
  const index = currentIdx >= 0 ? currentIdx : stamped >= 0 ? stamped : siblings.length
  addSubstepAt(parent, action === 'substep-before' ? index : index + 1)
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
      class="flow-map-add-overlay"
      :style="overlayStyle"
      aria-hidden="false"
    >
      <button
        v-for="handle in handles"
        :key="`${handle.action}-${handle.left}-${handle.top}`"
        type="button"
        class="flow-map-add-overlay__btn"
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
.flow-map-add-overlay {
  --flow-eb-scale: 1;
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 4500;
}

.flow-map-add-overlay__btn {
  position: fixed;
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(16px * var(--flow-eb-scale));
  height: calc(16px * var(--flow-eb-scale));
  margin: 0;
  padding: 0;
  border: 1px solid #cbd5e1;
  border-radius: 50%;
  background: #fff;
  color: #64748b;
  font-size: calc(12px * var(--flow-eb-scale));
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

.flow-map-add-overlay__btn:hover {
  transform: translate(-50%, -50%) scale(1.08);
  background: #e2e8f0;
  border-color: #94a3b8;
  color: #475569;
}
</style>
