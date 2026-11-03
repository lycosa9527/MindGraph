<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { storeToRefs } from 'pinia'

import { CanvasChrome, CanvasTopBar, MindMapSidePanel, ZoomControls } from '@/components/canvas'
import DiagramCanvasHost from '@/components/diagram/DiagramCanvasHost.vue'
import DiagramSessionProvider from '@/components/diagram/DiagramSessionProvider.vue'
import { OnlineCollabModal } from '@/components/workshop'
import { normalizeDiagramTypeKey } from '@/composables/canvasPage/newCanvasBootstrap'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { eventBus } from '@/composables/core/useEventBus'
import {
  bindBuilderDiagramSession,
  builderDiagramNodes,
  frameDiagramSession,
  isBoundToStep,
  registerBuilderFrameTarget,
  sameBoundStep,
  trainingStepKey,
} from '@/composables/training/builderDiagramBridge'
import {
  preferMindMapTreeIfRicher,
  readStepDiagramSpec,
  releaseBuilderDiagramBinding,
  writeStepDiagramSpec,
} from '@/composables/training/trainingCanvasSpec'
import { useTrainingDeckNav } from '@/composables/training/trainingDeckNav'
import {
  bindTrainingDragSurface,
  clearTrainingDragMarks,
  closeTrainingDragHint,
  trainingDragDropActive,
  trainingDragFilledIds,
  trainingDragHint,
  trainingDragKnockActive,
  trainingDragMarks,
  trainingDragPicking,
} from '@/composables/training/trainingDragKnock'
import { readFocusNodeId, readInteract } from '@/composables/training/trainingInteract'
import { alignInteractWithDiagram } from '@/composables/training/trainingInteractAlign'
import { applyTrainingTopicToDiagram } from '@/composables/training/trainingTopicApply'
import { TRAINING_LOCK_SCOPE, registerTrainingUiLock } from '@/composables/training/trainingUiLock'
import type { DiagramSession } from '@/stores/diagram'
import { defaultTemplateForUi } from '@/stores/specLoader/defaultTemplates'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import { useUIStore } from '@/stores/ui'
import type { MindMapCanvasMode } from '@/stores/ui'
import type { DiagramType } from '@/types'
import type { TrainingCourseStep } from '@/types/training'
import {
  readEffectiveMindMapCanvasMode,
  resolveSessionMindMapCanvasMode,
} from '@/utils/mindMapCanvasMode'
import { cloneShowcaseDiagramSpec } from '@/utils/showcaseDiagramThumbnail'
import { isTrainingBuilderPath } from '@/utils/trainingClient'

const props = withDefaults(
  defineProps<{
    diagramType?: string | null
    interactive?: boolean
    /** The builder canvas owns the walk list. Playback must not replace it. */
    publishBridge?: boolean
    /** Frame the guided-reading node instead of the whole diagram. */
    followWalk?: boolean
    step?: TrainingCourseStep | null
  }>(),
  { publishBridge: true, followWalk: false, step: null }
)

const route = useRoute()
const uiStore = useUIStore()
const { previewing } = storeToRefs(useTrainingBuilderStore())
const deckNav = useTrainingDeckNav()
const mergedRibbon = computed(() => isTrainingBuilderPath(route.path))
const lockScope = inject(TRAINING_LOCK_SCOPE, '')

const normalizedType = computed(() => {
  const key = normalizeDiagramTypeKey(props.diagramType) || 'mindmap'
  return key as DiagramType
})

const spec = ref<Record<string, unknown> | null>(null)
const { activeTool, closeActiveTool } = useMindMapSideToolbarState()

const sessionMode = computed<MindMapCanvasMode>(() =>
  resolveSessionMindMapCanvasMode(readEffectiveMindMapCanvasMode())
)
const sessionKey = computed(
  () =>
    `${trainingStepKey(props.step) || 'pos-x'}:${normalizedType.value}:${sessionMode.value}:${
      props.interactive ? 'edit' : 'ro'
    }`
)

function hydrateSpec(): Record<string, unknown> | null {
  const stored = readStepDiagramSpec(props.step)
  if (stored) return cloneShowcaseDiagramSpec(preferMindMapTreeIfRicher(stored))
  return defaultTemplateForUi(normalizedType.value, uiStore)
}

const collabOpen = ref(false)
const handToolActive = ref(false)
const providerRef = ref<{ session: DiagramSession } | null>(null)
const owner = `TrainingCanvasPreview:${Math.random().toString(36).slice(2, 8)}`

watch(
  () => props.step,
  (step, previous) => {
    const session = providerRef.value?.session
    if (!props.publishBridge || !session) return
    if (previous && !sameBoundStep(previous, step)) {
      if (props.interactive && isBoundToStep(previous)) {
        writeStepDiagramSpec(previous, session)
      }
      return
    }
    bindBuilderDiagramSession(session, step)
  }
)

watch(
  sessionKey,
  () => {
    spec.value = hydrateSpec()
  },
  { immediate: true }
)

const walkNodeId = computed(() => (props.step ? readFocusNodeId(props.step) : null))

const publishedNodeRecord = computed(() => {
  if (!props.publishBridge) return ''
  const nodes = providerRef.value?.session.data?.nodes ?? []
  return nodes.map((node) => `${node.id}\0${(node.text || '').trim()}`).join('|')
})

watch(
  () => providerRef.value?.session ?? null,
  (session) => {
    if (!props.publishBridge) return
    bindBuilderDiagramSession(session, props.step)
  }
)

watch(publishedNodeRecord, () => {
  if (!props.publishBridge) return
  const session = providerRef.value?.session
  if (!session || !isBoundToStep(props.step)) return
  const nodes = (session.data?.nodes ?? [])
    .filter((node) => node.id)
    .map((node) => ({ id: node.id, text: node.text.trim() || node.id }))
  builderDiagramNodes.value = nodes
  if (!props.interactive || !props.step || nodes.length === 0) return
  alignInteractWithDiagram(props.step, nodes)
})

watch(
  () => (props.followWalk ? (providerRef.value?.session ?? null) : null),
  (session, _previous, onCleanup) => {
    if (!session) return
    const release = registerBuilderFrameTarget(session)
    onCleanup(release)
    const nodeId = walkNodeId.value
    if (nodeId) frameDiagramSession(session, nodeId, 0)
  }
)

watch(
  () => {
    const interact = props.step ? readInteract(props.step) : null
    return {
      drag: interact?.mode === 'drag',
      saved: interact?.sequence_saved === true,
      blankCount: interact?.mode === 'drag' ? interact.blanks.length : 0,
      authoring: props.publishBridge,
      playing: previewing.value,
      picking: trainingDragPicking.value,
    }
  },
  (surface) => {
    const playingSurface = !surface.authoring || surface.playing
    if (!surface.drag) {
      if (props.step) bindTrainingDragSurface(null)
      trainingDragKnockActive.value = false
      trainingDragDropActive.value = false
      return
    }
    bindTrainingDragSurface(props.step ?? null, playingSurface)
    trainingDragKnockActive.value = surface.authoring && !surface.playing && surface.picking
    trainingDragDropActive.value = playingSurface && surface.saved && surface.blankCount > 0
    if (!surface.playing) {
      if (trainingDragHint.value && !trainingDragHint.value.editable) closeTrainingDragHint()
      clearTrainingDragMarks()
      return
    }
    const ids = new Set(
      (props.step ? readInteract(props.step)?.blanks : [])?.map((row) => row.node_id) ?? []
    )
    trainingDragMarks.value = Object.fromEntries(
      Object.entries(trainingDragMarks.value).filter(([id]) => ids.has(id))
    )
    trainingDragFilledIds.value = trainingDragFilledIds.value.filter((id) => ids.has(id))
  },
  { immediate: true }
)

watch(walkNodeId, (nodeId) => {
  const session = props.followWalk ? providerRef.value?.session : null
  if (!session || !nodeId) return
  frameDiagramSession(session, nodeId, 0)
})

const releaseCollabLock = registerTrainingUiLock({
  key: 'online-collab',
  scope: lockScope,
  isOpen: () => collabOpen.value,
  setOpen: (open: boolean) => {
    collabOpen.value = open
  },
})

onMounted(() => {
  eventBus.onWithOwner(
    'training:topic_apply_requested',
    ({ option }) => {
      const session = providerRef.value?.session
      if (session) applyTrainingTopicToDiagram(session, option)
    },
    owner
  )
  eventBus.onWithOwner(
    'training:modal_open_requested',
    ({ key }) => {
      if (key === 'online-collab') collabOpen.value = true
    },
    owner
  )
  eventBus.onWithOwner(
    'training:modal_close_requested',
    () => {
      collabOpen.value = false
    },
    owner
  )
})

function previewViewBus() {
  return providerRef.value?.session.viewBus ?? null
}

function onFitCanvas(): void {
  previewViewBus()?.emit('view:fit_to_canvas_requested', { animate: true, userInitiated: true })
}

function onHandToolToggle(active: boolean): void {
  handToolActive.value = active
}

onUnmounted(() => {
  if (trainingDragHint.value && !trainingDragHint.value.editable) closeTrainingDragHint()
  bindTrainingDragSurface(null)
  trainingDragKnockActive.value = false
  trainingDragDropActive.value = false
  releaseCollabLock()
  eventBus.removeAllListenersForOwner(owner)
  if (!props.publishBridge) return
  const session = providerRef.value?.session
  if (session && props.step && props.interactive && isBoundToStep(props.step)) {
    writeStepDiagramSpec(props.step, session)
  }
  releaseBuilderDiagramBinding(session ?? null, props.step)
})
</script>

<template>
  <div class="canvas-preview">
    <DiagramSessionProvider
      v-if="spec"
      ref="providerRef"
      :key="sessionKey"
      :mode="interactive ? 'edit' : 'readonly'"
      :mind-map-canvas-mode="sessionMode"
      :spec="spec"
      :diagram-type="normalizedType"
    >
      <CanvasChrome
        v-if="publishBridge"
        :class="{ 'is-merged-ribbon': mergedRibbon }"
      >
        <CanvasTopBar :preview-lock="!deckNav" />
      </CanvasChrome>
      <div class="canvas-preview__body">
        <DiagramCanvasHost
          class="canvas-preview__host"
          :show-minimap="false"
          :fit-view-on-init="!followWalk"
          :hand-tool-active="handToolActive || !interactive"
          :presentation-hand-pan-mode="!interactive"
        />
        <ZoomControls
          class="canvas-preview__zoom"
          minimal
          :hand-tool-active="handToolActive || !interactive"
          @hand-tool-toggle="onHandToolToggle"
          @fit-to-screen="onFitCanvas"
        />
        <MindMapSidePanel
          v-if="publishBridge && activeTool"
          class="canvas-preview__side"
          :tool="activeTool"
          @close="closeActiveTool"
        />
      </div>
      <OnlineCollabModal
        :visible="collabOpen"
        :diagram-id="null"
        mode="organization"
        @update:visible="collabOpen = $event"
      />
    </DiagramSessionProvider>
  </div>
</template>

<style scoped>
.canvas-preview {
  display: flex;
  height: 100%;
  min-height: 8rem;
  flex-direction: column;
  background: #f8fafc;
}
.canvas-preview :deep(.canvas-chrome.is-merged-ribbon) {
  display: none;
}
.canvas-preview__body {
  position: relative;
  min-height: 0;
  flex: 1;
}
.canvas-preview__host {
  height: 100%;
  min-height: 8rem;
}
.canvas-preview :deep(.diagram-canvas) {
  height: 100%;
  min-height: 8rem;
}
.canvas-preview__zoom {
  position: absolute;
  right: 0.75rem;
  bottom: 0.75rem;
  z-index: 4;
}
.canvas-preview__side {
  position: absolute;
  inset: 0;
  z-index: 8;
  pointer-events: none;
}
.canvas-preview__side :deep(.mind-map-side-panel),
.canvas-preview__side :deep(.mind-map-waterfall-panel),
.canvas-preview__side :deep(.ai-brainstorm-panel) {
  pointer-events: auto;
}
</style>
