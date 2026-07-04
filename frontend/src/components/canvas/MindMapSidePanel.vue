<script setup lang="ts">
/**
 * Mind-map side tool panels — outline delegates to SidebarOutline; other tools inline.
 */
import { computed } from 'vue'

import { Hammer, RotateCcw, Shuffle } from '@lucide/vue'

import MindMapSidePanelCloseButton from '@/components/canvas/MindMapSidePanelCloseButton.vue'

import { useLanguage } from '@/composables'
import { type MindMapSideToolId } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { useLearningSheetCustomMode } from '@/composables/mindMap/useLearningSheetCustomMode'

import MindMapDocumentSummaryPanel from './MindMapDocumentSummaryPanel.vue'
import MindMapOneSentencePanel from './MindMapOneSentencePanel.vue'
import MindMapWaterfallPanel from './MindMapWaterfallPanel.vue'
import SidebarOutline from './SidebarOutline.vue'

const props = defineProps<{
  tool: MindMapSideToolId
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()

const {
  isPickActive,
  isLearningSheetActive,
  activatePick,
  startRandomLearningSheet,
  exitLearningSheet,
} = useLearningSheetCustomMode()

const panelTitle = computed(() => {
  switch (props.tool) {
    case 'learning_sheet':
      return t('canvas.mindMapSideToolbar.learningSheet')
    case 'document_summary':
      return t('canvas.mindMapSideToolbar.documentSummary')
    case 'one_sentence':
      return t('canvas.mindMapSideToolbar.oneSentence')
    case 'waterfall':
      return t('canvas.mindMapSideToolbar.waterfall')
    default:
      return t('canvas.mindMapSideToolbar.outline')
  }
})

function handleClose(): void {
  emit('close')
}

function handleRandomLearningSheet(): void {
  startRandomLearningSheet()
}

function handleCustomPick(): void {
  activatePick()
}

function handleExitLearningSheet(): void {
  exitLearningSheet()
}
</script>

<template>
  <SidebarOutline
    v-if="tool === 'outline'"
    @close="handleClose"
  />

  <MindMapWaterfallPanel
    v-else-if="tool === 'waterfall'"
    @close="handleClose"
  />

  <MindMapOneSentencePanel
    v-else-if="tool === 'one_sentence'"
    @close="handleClose"
  />

  <MindMapDocumentSummaryPanel
    v-else-if="tool === 'document_summary'"
    @close="handleClose"
  />

  <aside
    v-else
    class="mind-map-side-panel pointer-events-auto absolute inset-y-3 left-3 z-40 flex w-80 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    :aria-label="panelTitle"
  >
    <header
      class="flex shrink-0 items-center justify-between gap-2 border-b border-slate-100 bg-gray-50/50 px-3 py-3"
    >
      <h3 class="truncate text-sm font-semibold tracking-wide text-gray-800">
        {{ panelTitle }}
      </h3>
      <MindMapSidePanelCloseButton @close="handleClose" />
    </header>

    <!-- Learning sheet -->
    <div
      v-if="tool === 'learning_sheet'"
      class="flex min-h-0 flex-1 flex-col overflow-y-auto"
    >
      <div class="flex flex-col gap-3 px-4 py-5">
        <p class="text-xs leading-relaxed text-gray-500">
          {{ t('canvas.mindMapSideToolbar.learningSheetIntro') }}
        </p>

        <button
          type="button"
          class="learning-sheet-mode-card group"
          @click="handleRandomLearningSheet"
        >
          <span class="learning-sheet-mode-card__icon learning-sheet-mode-card__icon--amber">
            <Shuffle
              class="h-4 w-4"
              :stroke-width="2"
            />
          </span>
          <span class="min-w-0 flex-1 text-left">
            <span class="block text-sm font-semibold text-slate-800">
              {{ t('canvas.mindMapSideToolbar.learningSheetRandomTitle') }}
            </span>
            <span class="mt-0.5 block text-[11px] leading-snug text-slate-500">
              {{ t('canvas.mindMapSideToolbar.learningSheetRandomDesc') }}
            </span>
          </span>
        </button>

        <button
          type="button"
          class="learning-sheet-mode-card group"
          :class="{ 'learning-sheet-mode-card--active': isPickActive }"
          @click="handleCustomPick"
        >
          <span class="learning-sheet-mode-card__icon learning-sheet-mode-card__icon--blue">
            <Hammer
              class="h-4 w-4 -rotate-[38deg]"
              :stroke-width="2"
            />
          </span>
          <span class="min-w-0 flex-1 text-left">
            <span class="block text-sm font-semibold text-slate-800">
              {{ t('canvas.mindMapSideToolbar.learningSheetCustomTitle') }}
            </span>
            <span class="mt-0.5 block text-[11px] leading-snug text-slate-500">
              {{ t('canvas.mindMapSideToolbar.learningSheetCustomDesc') }}
            </span>
          </span>
        </button>

        <button
          v-if="isLearningSheetActive"
          type="button"
          class="learning-sheet-restore-btn mt-1 inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors"
          @click="handleExitLearningSheet"
        >
          <RotateCcw
            class="h-4 w-4"
            :stroke-width="2.25"
          />
          {{ t('canvas.mindMapSideToolbar.restoreFullDiagram') }}
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.mind-map-side-panel {
  max-height: calc(100% - 1.5rem);
}

.learning-sheet-mode-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid rgb(226 232 240);
  border-radius: 14px;
  background: rgb(255 255 255);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.learning-sheet-mode-card:hover {
  border-color: rgb(203 213 225);
  background: rgb(248 250 252);
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.06);
}

.learning-sheet-mode-card__icon {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
}

.learning-sheet-mode-card__icon--amber {
  color: rgb(180 83 9);
  background: rgb(254 243 199);
}

.group:hover .learning-sheet-mode-card__icon--amber {
  background: rgb(253 230 138);
}

.learning-sheet-mode-card__icon--blue {
  color: rgb(29 78 216);
  background: rgb(219 234 254);
}

.group:hover .learning-sheet-mode-card__icon--blue {
  background: rgb(191 219 254);
}

.learning-sheet-mode-card--active {
  border-color: rgb(59 130 246);
  background: rgb(239 246 255);
  box-shadow: 0 0 0 1px rgb(59 130 246 / 0.25);
}

.learning-sheet-restore-btn {
  background: linear-gradient(180deg, rgb(245 158 11) 0%, rgb(217 119 6) 100%);
  border: 1px solid rgb(180 83 9 / 0.35);
}

.learning-sheet-restore-btn:hover {
  background: linear-gradient(180deg, rgb(251 191 36) 0%, rgb(245 158 11) 100%);
}
</style>
