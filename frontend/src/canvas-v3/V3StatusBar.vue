<script setup lang="ts">
/**
 * V3 status bar — node count, LLM pills, Word-style zoom cluster.
 */
import { computed } from 'vue'

import { Hand, Languages, ListTree, Maximize2, MonitorPlay } from '@lucide/vue'

import CanvasMindMapShortcutGuide from '@/components/canvas/CanvasMindMapShortcutGuide.vue'
import CanvasToolbarMindMapAiGenerate from '@/components/canvas/CanvasToolbarMindMapAiGenerate.vue'
import CanvasToolbarMindMapAudiencePicker from '@/components/canvas/CanvasToolbarMindMapAudiencePicker.vue'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { useLanguage } from '@/composables/core/useLanguage'

import { useV3RibbonActions } from './useV3RibbonActions'
import './v3Chrome.css'
import './v3Ribbon.css'

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
const actions = useV3RibbonActions()
const { activeTool, handleToolSelect } = useMindMapSideToolbarState()

const zoomPercent = computed(() => (props.zoom != null ? Math.round(props.zoom * 100) : 100))
</script>

<template>
  <div
    class="v3-status"
    data-testid="mindmap-v3-status-bar"
  >
    <div class="v3-status__left">
      <button
        type="button"
        class="v3-status__zoom-btn"
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
      <span class="v3-status__sep" />
      <span>{{ t('canvas.v3.nodeCount', { count: actions.nodeCount }) }}</span>
      <span class="v3-status__sep" />
      <CanvasMindMapShortcutGuide variant="status" />
    </div>
    <div class="v3-status__center">
      <CanvasToolbarMindMapAudiencePicker
        anchor="bottom"
        hide-guide
      />
      <span class="v3-status__label">{{ t('canvas.v3.aiModel') }}</span>
      <div class="v3-llm-selector">
        <button
          v-for="model in actions.llmModels"
          :key="model.id"
          type="button"
          class="v3-llm-btn"
          :data-llm="model.id"
          :class="{ 'is-active': actions.selectedLlm === model.id }"
          @click="actions.selectLlm(model.id)"
        >
          {{ model.label }}
        </button>
      </div>
      <CanvasToolbarMindMapAiGenerate tooltip-placement="top" />
    </div>
    <div class="v3-status__right v3-status__zoom">
      <button
        type="button"
        class="v3-status__zoom-btn"
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
        class="v3-status__zoom-btn"
        :class="{ 'is-active': handToolActive }"
        :title="t('canvas.zoomControls.hand')"
        data-testid="mindmap-v3-hand-tool"
        :aria-label="t('canvas.zoomControls.hand')"
        @click="actions.toggleHand(!handToolActive)"
      >
        <Hand
          class="h-3.5 w-3.5"
          :stroke-width="2"
        />
      </button>
      <span class="v3-status__sep" />
      <button
        type="button"
        class="v3-status__zoom-btn"
        data-testid="mindmap-v3-zoom-out"
        @click="actions.zoomOut"
      >
        −
      </button>
      <input
        class="v3-status__zoom-slider"
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
        class="v3-status__zoom-btn"
        data-testid="mindmap-v3-zoom-in"
        @click="actions.zoomIn"
      >
        +
      </button>
      <span data-testid="mindmap-v3-zoom-percent">{{ zoomPercent }}%</span>
      <button
        type="button"
        class="v3-status__zoom-btn"
        :title="t('canvas.v3.resetView')"
        :aria-label="t('canvas.v3.resetView')"
        data-testid="mindmap-v3-fit-view"
        @click="actions.fitToScreen"
      >
        <Maximize2
          class="h-3.5 w-3.5"
          :stroke-width="2"
        />
      </button>
      <button
        type="button"
        class="v3-status__zoom-btn"
        :title="t('canvas.zoomControls.presentationMode')"
        :aria-label="t('canvas.zoomControls.presentationMode')"
        data-testid="mindmap-v3-presentation"
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
