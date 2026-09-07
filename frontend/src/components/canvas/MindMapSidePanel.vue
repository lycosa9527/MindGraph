<script setup lang="ts">
/**
 * Mind-map side tool panels — outline delegates to SidebarOutline; other tools inline.
 */
import { computed, watch } from 'vue'

import { Hammer, Shuffle } from '@lucide/vue'

import AiGenerateGlassHero from '@/components/canvas/AiGenerateGlassHero.vue'

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
  activatePick,
  startRandomLearningSheet,
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

watch(
  () => props.tool,
  (tool, _previous, onCleanup) => {
    if (tool !== 'document_summary' && tool !== 'learning_sheet') return
    const onKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') handleClose()
    }
    window.addEventListener('keydown', onKeydown)
    onCleanup(() => window.removeEventListener('keydown', onKeydown))
  },
  { immediate: true }
)

function handleRandomLearningSheet(): void {
  const keepAnswers = diagramStore.learningSheetShowAnswers
  startRandomLearningSheet()
  diagramStore.setLearningSheetShowAnswers(keepAnswers)
  handleClose()
}

function handleCustomPick(): void {
  const keepAnswers = diagramStore.learningSheetShowAnswers
  activatePick()
  diagramStore.setLearningSheetShowAnswers(keepAnswers)
  handleClose()
}

function onKeepAnswersChange(value: string | number | boolean): void {
  diagramStore.setLearningSheetShowAnswers(Boolean(value))
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

  <Teleport
    v-else-if="tool === 'document_summary'"
    to="body"
  >
    <div
      class="mm-canvas-center-modal"
      role="presentation"
      @click.self="handleClose"
    >
      <MindMapDocumentSummaryPanel @close="handleClose" />
    </div>
  </Teleport>

  <Teleport
    v-else-if="tool === 'learning_sheet'"
    to="body"
  >
    <div
      class="mm-canvas-center-modal"
      role="presentation"
      @click.self="handleClose"
    >
      <aside
        class="mind-map-side-rail-panel mind-map-side-panel learning-sheet-glass-panel pointer-events-auto ai-gen-shell ai-gen-shell--learningSheet"
        :aria-label="panelTitle"
      >
        <AiGenerateGlassHero
          variant="learningSheet"
          @close="handleClose"
        />

        <div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
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

            <label class="learning-sheet-keep-answers">
              <span class="learning-sheet-keep-answers__copy">
                <span class="learning-sheet-keep-answers__label">
                  {{ t('canvas.mindMapSideToolbar.learningSheetKeepAnswers') }}
                </span>
                <span class="learning-sheet-keep-answers__hint">
                  {{ t('canvas.mindMapSideToolbar.learningSheetKeepAnswersHint') }}
                </span>
              </span>
              <el-switch
                :model-value="diagramStore.learningSheetShowAnswers"
                @change="onKeepAnswersChange"
              />
            </label>
          </div>
        </div>
      </aside>
    </div>
  </Teleport>
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

.learning-sheet-keep-answers {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 4px;
  padding: 10px 12px;
  border: 1px solid var(--swiss-border, #e7e5e4);
  border-radius: 12px;
  background: var(--swiss-inset, #fafaf9);
  cursor: pointer;
}

.learning-sheet-keep-answers__copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.learning-sheet-keep-answers__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--swiss-ink, #1c1917);
}

.learning-sheet-keep-answers__hint {
  font-size: 11px;
  line-height: 1.35;
  color: var(--swiss-muted, #78716c);
}

.learning-sheet-mode-card--active {
  border-color: var(--swiss-ink, #1c1917);
  background: var(--swiss-hover, #f5f5f4);
  box-shadow: 0 0 0 1px var(--swiss-ink, #1c1917);
}
</style>
