<script setup lang="ts">
/**
 * Status bar — node count, LLM pills, zoom cluster.
 */
import { computed } from 'vue'

import { Hand, Languages, ListTree, Maximize2, MonitorPlay } from '@lucide/vue'

import CanvasMindMapShortcutGuide from '@/components/canvas/CanvasMindMapShortcutGuide.vue'
import CanvasToolbarMindMapAiGenerate from '@/components/canvas/CanvasToolbarMindMapAiGenerate.vue'
import CanvasToolbarMindMapAudiencePicker from '@/components/canvas/CanvasToolbarMindMapAudiencePicker.vue'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { useLanguage } from '@/composables/core/useLanguage'

import { useMindMapRibbonActions } from './useMindMapRibbonActions'
import './mindMapStatusBar.css'
import './mindMapRibbon.css'

const props = withDefaults(
  defineProps<{
    zoom?: number | null
    handToolActive?: boolean
  }>(),
  {
    zoom: null,
    handToolActive: false,
  }
)

const { t } = useLanguage()
const actions = useMindMapRibbonActions()
const { activeTool, handleToolSelect } = useMindMapSideToolbarState()

const zoomPercent = computed(() => (props.zoom != null ? Math.round(props.zoom * 100) : 100))
</script>

<template>
  <div
    class="mm-status"
    data-testid="mindmap-ribbon-status-bar"
  >
    <div class="mm-status__left">
      <button
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
        {{ t('canvas.mindMapSideToolbar.outline') }}
      </button>
      <span class="mm-status__sep" />
      <span>{{ t('canvas.ribbon.nodeCount', { count: actions.nodeCount }) }}</span>
      <span class="mm-status__sep" />
      <CanvasMindMapShortcutGuide variant="status" />
    </div>
    <div class="mm-status__center">
      <CanvasToolbarMindMapAudiencePicker
        anchor="bottom"
        hide-guide
      />
      <span class="mm-status__label">{{ t('canvas.ribbon.aiModel') }}</span>
      <div class="mm-llm-selector">
        <button
          v-for="model in actions.llmModels"
          :key="model.id"
          type="button"
          class="mm-llm-btn"
          :data-llm="model.id"
          :class="{ 'is-active': actions.selectedLlm === model.id }"
          @click="actions.selectLlm(model.id)"
        >
          {{ model.label }}
        </button>
      </div>
      <CanvasToolbarMindMapAiGenerate tooltip-placement="top" />
    </div>
    <div class="mm-status__right mm-status__zoom">
      <button
        type="button"
        class="mm-status__zoom-btn"
        :title="t('canvas.toolbar.moreAppTranslateLabelDesc')"
        :aria-label="t('canvas.toolbar.moreAppTranslateLabel')"
        @click="actions.runTranslate"
      >
        {{ t('canvas.toolbar.moreAppTranslateLabel') }}
        <Languages
          class="h-3.5 w-3.5"
          :stroke-width="2"
        />
      </button>
      <button
        type="button"
        class="mm-status__zoom-btn"
        :class="{ 'is-active': handToolActive }"
        :title="t('canvas.zoomControls.hand')"
        data-testid="mindmap-ribbon-hand-tool"
        :aria-label="t('canvas.zoomControls.hand')"
        @click="actions.toggleHand(!handToolActive)"
      >
        <Hand
          class="h-3.5 w-3.5"
          :stroke-width="2"
        />
      </button>
      <span class="mm-status__sep" />
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
