<script setup lang="ts">
/**
 * Mind-map side tool panels — outline delegates to SidebarOutline; other tools inline.
 */
import { computed } from 'vue'

import { Hammer, RotateCcw, Shuffle } from '@lucide/vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import MindMapSidePanelHeader from '@/components/canvas/MindMapSidePanelHeader.vue'

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
    class="mind-map-side-rail-panel mind-map-side-panel pointer-events-auto w-80"
    :aria-label="panelTitle"
  >
    <MindMapSidePanelHeader
      :title="panelTitle"
      :intro="t('canvas.mindMapSideToolbar.learningSheetIntro')"
      @close="handleClose"
    />

    <!-- Learning sheet -->
    <div
      v-if="tool === 'learning_sheet'"
      class="flex min-h-0 flex-1 flex-col overflow-y-auto"
    >
      <div class="flex flex-col gap-3 px-4 py-5">
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
              class="h-4 w-4 rotate-[-38deg]"
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
            <AdminSwissSegmented
              v-model="answerVisibility"
              block
              :options="answerVisibilityOptions"
              :ariaLabel="t('canvas.mindMapSideToolbar.learningSheetAnswersLabel')"
            />
            <p class="learning-sheet-answers-control__shortcut">
              {{ t('canvas.mindMapSideToolbar.learningSheetAnswersShortcut') }}
            </p>
          </div>

          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--primary w-full"
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
.learning-sheet-mode-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--swiss-border, #e7e5e4);
  border-radius: 12px;
  background: var(--swiss-surface, #ffffff);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.learning-sheet-mode-card:hover {
  border-color: var(--swiss-border-strong, #d6d3d1);
  background: var(--swiss-hover, #f5f5f4);
}

.learning-sheet-mode-card__icon {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid var(--swiss-border, #e7e5e4);
  background: var(--swiss-inset, #fafaf9);
}

.learning-sheet-mode-card__icon--amber {
  color: var(--swiss-geek-amber-ui, #b45309);
  background: var(--swiss-geek-amber-soft, #fffbeb);
  border-color: color-mix(in srgb, var(--swiss-geek-amber-ui, #b45309) 22%, var(--swiss-border, #e7e5e4));
}

.learning-sheet-mode-card__icon--blue {
  color: var(--swiss-geek-cyan-ui, #0e7490);
  background: var(--swiss-geek-cyan-soft, #ecfeff);
  border-color: color-mix(in srgb, var(--swiss-geek-cyan-ui, #0e7490) 22%, var(--swiss-border, #e7e5e4));
}

.learning-sheet-mode-card--active {
  border-color: var(--swiss-ink, #1c1917);
  background: var(--swiss-hover, #f5f5f4);
  box-shadow: 0 0 0 1px var(--swiss-ink, #1c1917);
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
  color: var(--swiss-muted, #78716c);
}

.learning-sheet-answers-control__shortcut {
  margin: 0;
  font-size: 10px;
  line-height: 1.35;
  color: var(--swiss-subtle, #a8a29e);
}
</style>
