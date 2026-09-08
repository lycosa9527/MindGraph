<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { CanvasChrome, CanvasTopBar, ZoomControls } from '@/components/canvas'
import { OnlineCollabModal } from '@/components/workshop'
import { eventBus } from '@/composables/core/useEventBus'
import { applyTrainingTopicToDiagram } from '@/composables/training/trainingTopicApply'
import DiagramCanvasHost from '@/components/diagram/DiagramCanvasHost.vue'
import DiagramSessionProvider from '@/components/diagram/DiagramSessionProvider.vue'
import { normalizeDiagramTypeKey } from '@/composables/canvasPage/newCanvasBootstrap'
import type { LocaleCode } from '@/i18n/locales'
import type { DiagramSession } from '@/stores/diagram'
import { getDefaultTemplate } from '@/stores/specLoader/defaultTemplates'
import { useUIStore } from '@/stores/ui'
import type { MindMapCanvasMode } from '@/stores/ui'
import type { DiagramType } from '@/types'
import {
  readEffectiveMindMapCanvasMode,
  resolveSessionMindMapCanvasMode,
} from '@/utils/mindMapCanvasMode'

const props = defineProps<{
  diagramType?: string | null
  canvasMode?: MindMapCanvasMode | null
  interactive?: boolean
}>()

const uiStore = useUIStore()

const normalizedType = computed(() => {
  const key = normalizeDiagramTypeKey(props.diagramType) || 'mindmap'
  return key as DiagramType
})

const spec = computed(() =>
  getDefaultTemplate(normalizedType.value, uiStore.language as LocaleCode)
)

const sessionMode = computed<MindMapCanvasMode>(() =>
  resolveSessionMindMapCanvasMode(props.canvasMode || readEffectiveMindMapCanvasMode())
)
const sessionKey = computed(
  () =>
    `${normalizedType.value}:${sessionMode.value}:${props.interactive ? 'edit' : 'ro'}:${spec.value ? 'ok' : 'empty'}`
)

const collabOpen = ref(false)
const providerRef = ref<{ session: DiagramSession } | null>(null)
const owner = `TrainingCanvasPreview:${Math.random().toString(36).slice(2, 8)}`

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

onUnmounted(() => {
  eventBus.removeAllListenersForOwner(owner)
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
      <CanvasChrome>
        <CanvasTopBar preview-lock />
      </CanvasChrome>
      <div class="canvas-preview__body">
        <DiagramCanvasHost
          class="canvas-preview__host"
          :show-minimap="false"
          :fit-view-on-init="true"
          :hand-tool-active="!interactive"
          :presentation-hand-pan-mode="!interactive"
        />
        <ZoomControls class="canvas-preview__zoom" />
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
</style>
