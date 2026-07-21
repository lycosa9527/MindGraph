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
import { useDiagramStore } from '@/stores'

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
const diagramStore = useDiagramStore()

const {
  isPickActive,
  isLearningSheetActive,
  activatePick,
  startRandomLearningSheet,
  exitLearningSheet,
} = useLearningSheetCustomMode()

type AnswerVisibility = 'show' | 'hide'

const answerVisibility = computed<AnswerVisibility>({
  get: () => (diagramStore.learningSheetShowAnswers ? 'show' : 'hide'),
  set: (value) => {
    diagramStore.setLearningSheetShowAnswers(value === 'show')
  },
})

const answerVisibilityOptions = computed(() => [
  { label: t('canvas.mindMapSideToolbar.learningSheetAnswersShow'), value: 'show' as const },
  { label: t('canvas.mindMapSideToolbar.learningSheetAnswersHide'), value: 'hide' as const },
])

function setAnswerVisibility(value: AnswerVisibility): void {
  answerVisibility.value = value
}

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
      <h3 class="truncate text-base font-semibold tracking-wide text-gray-800">
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
        <p class="text-sm leading-relaxed text-gray-500">
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

        <div
          v-if="isLearningSheetActive"
          class="learning-sheet-session-controls mt-1 flex flex-col gap-2"
        >
          <div class="learning-sheet-answers-control">
            <span class="learning-sheet-answers-control__label">
              {{ t('canvas.mindMapSideToolbar.learningSheetAnswersLabel') }}
            </span>
            <div
              class="learning-sheet-answers-seg"
              role="radiogroup"
              :aria-label="t('canvas.mindMapSideToolbar.learningSheetAnswersLabel')"
            >
              <button
                v-for="opt in answerVisibilityOptions"
                :key="opt.value"
                type="button"
                role="radio"
                class="learning-sheet-answers-seg__btn"
                :class="{ 'is-active': answerVisibility === opt.value }"
                :aria-checked="answerVisibility === opt.value"
                @click="setAnswerVisibility(opt.value)"
              >
                {{ opt.label }}
              </button>
            </div>
            <p class="learning-sheet-answers-control__shortcut">
              {{ t('canvas.mindMapSideToolbar.learningSheetAnswersShortcut') }}
            </p>
          </div>

          <button
            type="button"
            class="learning-sheet-restore-btn inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors"
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

.learning-sheet-answers-control {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.learning-sheet-answers-control__label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: rgb(29 78 216);
}

.learning-sheet-answers-control__shortcut {
  margin: 0;
  font-size: 10px;
  line-height: 1.35;
  color: rgb(37 99 235 / 0.85);
}

.learning-sheet-answers-seg {
  display: flex;
  width: 100%;
  padding: 3px;
  gap: 3px;
  border-radius: 12px;
  border: 1px solid rgb(59 130 246 / 0.35);
  background: rgb(239 246 255);
  box-shadow: 0 1px 2px rgb(37 99 235 / 0.08);
}

.learning-sheet-answers-seg__btn {
  flex: 1 1 0;
  min-width: 0;
  margin: 0;
  padding: 0.5rem 0.75rem;
  border: none;
  border-radius: 9px;
  background: transparent;
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.35;
  color: rgb(29 78 216);
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.learning-sheet-answers-seg__btn:not(.is-active):hover {
  background: rgb(191 219 254 / 0.75);
}

.learning-sheet-answers-seg__btn.is-active {
  color: rgb(255 255 255);
  background: linear-gradient(180deg, rgb(59 130 246) 0%, rgb(37 99 235) 100%);
  box-shadow: 0 1px 2px rgb(29 78 216 / 0.28);
}

.learning-sheet-answers-seg__btn:focus {
  outline: none;
}

.learning-sheet-answers-seg__btn:focus-visible {
  outline: 2px solid rgb(59 130 246);
  outline-offset: 1px;
}
</style>
