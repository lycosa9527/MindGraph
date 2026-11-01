<script setup lang="ts">
/**
 * Status bar — node count, LLM pills, zoom cluster.
 * When the row does not fit, the AI button uses its short name, zoom
 * slider controls hide, and the other labeled controls keep their icons.
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { AppWindow, ListTree, Maximize2, MonitorPlay } from '@lucide/vue'

import { diagramRibbonCapabilities } from '@/canvas-ribbon/diagramRibbonCapabilities'
import CanvasMindMapGestureGuide from '@/components/canvas/CanvasMindMapGestureGuide.vue'
import CanvasMindMapShortcutGuide from '@/components/canvas/CanvasMindMapShortcutGuide.vue'
import CanvasToolbarMindMapAiGenerate from '@/components/canvas/CanvasToolbarMindMapAiGenerate.vue'
import CanvasToolbarMindMapAudiencePicker from '@/components/canvas/CanvasToolbarMindMapAudiencePicker.vue'
import I18nText from '@/components/common/I18nText.vue'
import { useClassroomRemoteVisibility } from '@/composables/canvas/useClassroomRemotePosition'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useLearningAiGate } from '@/composables/learningSpace/useLearningAiGate'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import { statusBarUsedWidth } from '@/utils/statusBarFit'
import {
  type LabelCollapseSnapshot,
  createLabelCollapseSnapshot,
  nextLabelCollapse,
} from '@/utils/toolbarLabelCollapse'

import CanvasDiagramTranslateLangPicker from './CanvasDiagramTranslateLangPicker.vue'
import CanvasLlmMenuDropdown from './CanvasLlmMenuDropdown.vue'
import './mindMapRibbon.css'
import './mindMapStatusBar.css'
import { useMindMapRibbonActions } from './useMindMapRibbonActions'

const props = withDefaults(
  defineProps<{
    zoom?: number | null
  }>(),
  {
    zoom: null,
  }
)

const { t, currentLanguage } = useLanguage()
const { showCanvasAiFeatures } = useLearningAiGate()
const diagramStore = useDiagramSession()
const mindMapV2 = useMindMapV2Chrome()
const caps = computed(() => diagramRibbonCapabilities(diagramStore.type, mindMapV2.value))
const actions = useMindMapRibbonActions()
const { hidden: classroomRemoteHidden, toggleHidden: toggleClassroomRemote } =
  useClassroomRemoteVisibility()
const { activeTool, handleToolSelect } = useMindMapSideToolbarState()

const zoomPercent = computed(() => (props.zoom != null ? Math.round(props.zoom * 100) : 100))

const barRef = ref<HTMLElement | null>(null)
const tight = ref(false)
let fitSnapshot: LabelCollapseSnapshot = createLabelCollapseSnapshot()
let fitObserver: ResizeObserver | null = null

function resetStatusFit(): void {
  fitSnapshot = createLabelCollapseSnapshot()
  tight.value = false
}

function observeStatusFit(): void {
  const bar = barRef.value
  if (!bar || !fitObserver) return
  fitObserver.observe(bar)
  for (const cluster of bar.children) {
    if (cluster instanceof HTMLElement) fitObserver.observe(cluster)
  }
}

function measureStatusFit(): void {
  const bar = barRef.value
  if (!bar) return
  const clientWidth = bar.clientWidth > 0 ? bar.clientWidth : -1
  const next = nextLabelCollapse(fitSnapshot, clientWidth, statusBarUsedWidth(bar))
  const changed = next.collapsed !== fitSnapshot.collapsed
  fitSnapshot = next
  tight.value = next.collapsed
  if (changed && !next.collapsed) {
    void nextTick(() => measureStatusFit())
  }
}

onMounted(() => {
  if (typeof ResizeObserver === 'undefined') return
  fitObserver = new ResizeObserver(() => measureStatusFit())
  observeStatusFit()
  measureStatusFit()
})

onUnmounted(() => {
  fitObserver?.disconnect()
  fitObserver = null
})

watch(
  () =>
    [
      currentLanguage.value,
      caps.value.outline,
      caps.value.gestureGuide,
      showCanvasAiFeatures.value,
    ] as const,
  async () => {
    resetStatusFit()
    await nextTick()
    observeStatusFit()
    measureStatusFit()
  }
)
</script>

<template>
  <div
    ref="barRef"
    class="mm-status"
    data-testid="mindmap-ribbon-status-bar"
  >
    <div class="mm-status__left">
      <button
        v-if="caps.outline"
        type="button"
        class="mm-status__zoom-btn"
        :class="{ 'is-active': activeTool === 'outline' }"
        :title="t('canvas.mindMapSideToolbar.outline')"
        @click="handleToolSelect('outline')"
      >
        <ListTree
          class="inline h-3.5 w-3.5"
          :stroke-width="2"
        />
        <I18nText
          v-if="!tight"
          k="canvas.mindMapSideToolbar.outline"
        />
      </button>
      <span
        v-if="caps.outline"
        class="mm-status__sep"
      />
      <span>
        <I18nText
          k="canvas.ribbon.nodeCount"
          :params="{ count: actions.nodeCount }"
        />
      </span>
      <span class="mm-status__sep" />
      <CanvasMindMapShortcutGuide :icon-only="tight" />
      <CanvasMindMapGestureGuide
        v-if="caps.gestureGuide"
        :icon-only="tight"
      />
    </div>
    <div
      v-if="showCanvasAiFeatures"
      class="mm-status__center"
    >
      <CanvasToolbarMindMapAudiencePicker
        anchor="bottom"
        hide-guide
        :compact="tight"
      />
      <span
        v-if="!tight"
        class="mm-status__label"
      >
        <I18nText k="canvas.ribbon.aiModel" />
      </span>
      <CanvasLlmMenuDropdown />
      <CanvasToolbarMindMapAiGenerate
        tooltip-placement="top"
        :short="tight"
      />
    </div>
    <div class="mm-status__right mm-status__zoom">
      <CanvasDiagramTranslateLangPicker v-if="showCanvasAiFeatures" />
      <button
        type="button"
        class="mm-status__zoom-btn"
        :class="{ 'is-active': !classroomRemoteHidden }"
        :title="t('canvas.classroomRemote.ariaLabel')"
        data-testid="mindmap-ribbon-floating-toolbar"
        :aria-label="t('canvas.classroomRemote.ariaLabel')"
        :aria-pressed="!classroomRemoteHidden"
        @click="toggleClassroomRemote"
      >
        <AppWindow
          class="h-3.5 w-3.5"
          :stroke-width="2"
        />
      </button>
      <span class="mm-status__sep" />
      <template v-if="!tight">
        <button
          type="button"
          class="mm-status__zoom-btn"
          data-testid="mindmap-ribbon-zoom-out"
          @click="actions.zoomOut"
        >
          −
        </button>
        <input
          class="mm-status__zoom-slider"
          type="range"
          min="25"
          max="200"
          step="1"
          :value="zoomPercent"
          :aria-valuemin="25"
          :aria-valuemax="200"
          :aria-valuenow="zoomPercent"
          :aria-label="`${zoomPercent}%`"
          @input="actions.zoomSet(Number(($event.target as HTMLInputElement).value))"
        />
        <button
          type="button"
          class="mm-status__zoom-btn"
          data-testid="mindmap-ribbon-zoom-in"
          @click="actions.zoomIn"
        >
          +
        </button>
        <span data-testid="mindmap-ribbon-zoom-percent">{{ zoomPercent }}%</span>
      </template>
      <button
        type="button"
        class="mm-status__zoom-btn"
        :title="t('canvas.ribbon.resetView')"
        :aria-label="t('canvas.ribbon.resetView')"
        data-testid="mindmap-ribbon-fit-view"
        @click="actions.fitToScreen"
      >
        <Maximize2
          class="h-3.5 w-3.5"
          :stroke-width="2"
        />
      </button>
      <button
        type="button"
        class="mm-status__zoom-btn"
        :title="t('canvas.zoomControls.presentationMode')"
        :aria-label="t('canvas.zoomControls.presentationMode')"
        data-testid="mindmap-ribbon-presentation"
        @click="actions.startPresentation"
      >
        <MonitorPlay
          class="h-3.5 w-3.5"
          :stroke-width="2"
        />
      </button>
    </div>
  </div>
</template>
