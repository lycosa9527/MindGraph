<script setup lang="ts">
/**
 * V3 status bar — node count, LLM pills, Word-style zoom cluster.
 */
import { computed } from 'vue'

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

const zoomPercent = computed(() => (props.zoom != null ? Math.round(props.zoom * 100) : 100))
</script>

<template>
  <div
    class="v3-status"
    data-testid="mindmap-v3-status-bar"
  >
    <div class="v3-status__left">
      <span>{{ t('canvas.v3.nodeCount', { count: actions.nodeCount }) }}</span>
      <span>{{ t('canvas.v3.editMode') }}</span>
    </div>
    <div class="v3-status__center">
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
    </div>
    <div class="v3-status__right v3-status__zoom">
      <button
        type="button"
        class="v3-status__zoom-btn"
        :class="{ 'is-active': handToolActive }"
        :title="t('canvas.zoomControls.hand')"
        data-testid="mindmap-v3-hand-tool"
        @click="actions.toggleHand(!handToolActive)"
      >
        {{ t('canvas.zoomControls.hand') }}
      </button>
      <button
        type="button"
        class="v3-status__zoom-btn"
        data-testid="mindmap-v3-zoom-out"
        @click="actions.zoomOut"
      >
        −
      </button>
      <span data-testid="mindmap-v3-zoom-percent">{{ zoomPercent }}%</span>
      <button
        type="button"
        class="v3-status__zoom-btn"
        data-testid="mindmap-v3-zoom-in"
        @click="actions.zoomIn"
      >
        +
      </button>
      <button
        type="button"
        class="v3-reset-view"
        data-testid="mindmap-v3-fit-view"
        @click="actions.fitToScreen"
      >
        {{ t('canvas.v3.resetView') }}
      </button>
    </div>
  </div>
</template>
