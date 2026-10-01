<script setup lang="ts">
/**
 * One demo diagram: default template for 1s, then the saved spec.
 */
import { computed, onBeforeUnmount, ref, shallowRef, toRef, watch } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import DiagramCanvasHost from '@/components/diagram/DiagramCanvasHost.vue'
import DiagramSessionProvider from '@/components/diagram/DiagramSessionProvider.vue'
import { DEMO_TEMPLATE_MS, type DemoPhase } from '@/composables/demo/demoPlayback'
import { type DemoTourSession, useDemoTour } from '@/composables/demo/useDemoTour'
import type { LocaleCode } from '@/i18n/locales'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { getDefaultTemplate } from '@/stores/specLoader/defaultTemplates'
import { useUIStore } from '@/stores/ui'
import type { DiagramType } from '@/types'
import { readShowcaseMindMapCanvasMode } from '@/utils/mindMapCanvasMode'
import {
  cloneShowcaseDiagramSpec,
  resolveShowcaseDiagramType,
} from '@/utils/showcaseDiagramThumbnail'

const props = defineProps<{
  diagramId: string
  diagramType: string
  phase: DemoPhase
  paused: boolean
  thumbnail: string | null
}>()

const emit = defineEmits<{
  tourDone: []
}>()

const rootRef = ref<HTMLElement | null>(null)
const providerRef = ref<{ session: DemoTourSession } | null>(null)

const savedDiagrams = useSavedDiagramsStore()
const uiStore = useUIStore()
const liveSpec = ref<Record<string, unknown> | null>(null)
const loadFailed = ref(false)
let specLoad = 0
const canvasMode = readShowcaseMindMapCanvasMode()

const normalizedType = computed(() => resolveShowcaseDiagramType(null, props.diagramType))

const templateSpec = computed(() =>
  getDefaultTemplate(normalizedType.value, uiStore.language as LocaleCode)
)

const shownSpec = computed(() => {
  if (props.phase === 'revealed' && liveSpec.value) return liveSpec.value
  return templateSpec.value
})

/** Plain spec for the preview session. A reactive spec plus the session's deep watch loops. */
const previewSpec = shallowRef<Record<string, unknown> | null>(null)

watch(
  shownSpec,
  (spec) => {
    previewSpec.value = spec ? cloneShowcaseDiagramSpec(spec) : null
  },
  { immediate: true }
)

const sessionKey = computed(() => {
  const source = props.phase === 'revealed' && liveSpec.value ? 'live' : 'template'
  return `${props.diagramId}:${source}`
})

const tourActive = computed(() => props.phase === 'revealed')
const specReady = computed(() => liveSpec.value != null)

const { focusNodeId, brightNodeIds } = useDemoTour({
  active: tourActive,
  paused: toRef(props, 'paused'),
  diagramType: normalizedType,
  ready: specReady,
  failed: loadFailed,
  getSession: () => providerRef.value?.session ?? null,
  canvasHeight: () => rootRef.value?.clientHeight ?? 0,
  onDone: () => emit('tourDone'),
})

watch(
  () => props.diagramId,
  (diagramId) => {
    const token = specLoad + 1
    specLoad = token
    liveSpec.value = null
    loadFailed.value = false
    const cached = savedDiagrams.getCachedDiagramSpec(diagramId)
    if (cached) {
      liveSpec.value = cloneShowcaseDiagramSpec(cached)
      return
    }
    void savedDiagrams.getDiagram(diagramId).then((result) => {
      if (token !== specLoad || diagramId !== props.diagramId) return
      if (!result.ok) {
        loadFailed.value = true
        return
      }
      liveSpec.value = cloneShowcaseDiagramSpec(result.diagram.spec)
    })
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  specLoad += 1
})
</script>

<template>
  <div
    ref="rootRef"
    class="demo-slide-canvas"
  >
    <div
      v-if="phase === 'template'"
      class="demo-slide-canvas__bar"
    >
      <span class="demo-slide-canvas__sr">
        <I18nText k="sidebar.demo.loading" />
      </span>
      <span
        class="demo-slide-canvas__fill"
        :class="{ 'is-paused': paused }"
        :style="{ animationDuration: `${DEMO_TEMPLATE_MS}ms` }"
      />
    </div>
    <div
      v-if="previewSpec"
      :key="sessionKey"
      class="demo-slide-canvas__frame"
    >
      <DiagramSessionProvider
        ref="providerRef"
        mode="readonly"
        :mind-map-canvas-mode="canvasMode"
        :spec="previewSpec"
        :diagram-type="normalizedType as DiagramType"
      >
        <DiagramCanvasHost
          class="demo-slide-canvas__host"
          :show-minimap="false"
          :fit-view-on-init="phase !== 'revealed'"
          :hand-tool-active="true"
          :presentation-hand-pan-mode="true"
          :mind-map-slide-focus-node-id="focusNodeId"
          :mind-map-slide-dim-focus-node-ids="brightNodeIds"
        />
      </DiagramSessionProvider>
    </div>
    <img
      v-else-if="loadFailed && thumbnail"
      :src="thumbnail"
      alt=""
      class="demo-slide-canvas__thumb"
    />
  </div>
</template>

<style scoped>
.demo-slide-canvas {
  position: relative;
  height: 100%;
  min-height: 0;
}

.demo-slide-canvas__frame,
.demo-slide-canvas__host {
  position: absolute;
  inset: 0;
}

.demo-slide-canvas__frame {
  animation: demo-canvas-in 420ms ease;
}

.demo-slide-canvas :deep(.vue-flow),
.demo-slide-canvas :deep(.diagram-canvas) {
  width: 100%;
  height: 100%;
  background: transparent;
}

.demo-slide-canvas :deep(.vue-flow__background) {
  opacity: 0.28;
}

.demo-slide-canvas__thumb {
  position: absolute;
  inset: 1rem;
  width: calc(100% - 2rem);
  height: calc(100% - 2rem);
  object-fit: contain;
}

.demo-slide-canvas__bar {
  position: absolute;
  right: 1.25rem;
  bottom: 0.9rem;
  left: 1.25rem;
  z-index: 2;
  height: 2px;
  overflow: hidden;
  background: rgb(28 25 23 / 0.14);
}

.demo-slide-canvas__sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}

.demo-slide-canvas__fill {
  display: block;
  width: 0;
  height: 100%;
  background: #1c1917;
  animation-name: demo-load;
  animation-timing-function: linear;
  animation-fill-mode: forwards;
}

.demo-slide-canvas__fill.is-paused {
  animation-play-state: paused;
}

@keyframes demo-load {
  to {
    width: 100%;
  }
}

@keyframes demo-canvas-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .demo-slide-canvas__frame {
    animation: none;
  }
}
</style>
