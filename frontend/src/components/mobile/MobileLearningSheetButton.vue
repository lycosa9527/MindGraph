<script setup lang="ts">
/**
 * Mobile 挖空支架图 — same random / custom blanking as the desktop learning sheet.
 * The print worksheet stays in the export sheet (制作学习单).
 */
import { onMounted, onUnmounted, ref } from 'vue'

import { Hammer, Shuffle } from '@lucide/vue'

import MindMapLearningSheetIcon from '@/components/canvas/MindMapLearningSheetIcon.vue'
import { useEventBus, useLanguage, useNotifications } from '@/composables'
import {
  resetLearningSheetCustomModeUi,
  restoreLearningSheetUiFromDiagram,
  useLearningSheetCustomMode,
  useLearningSheetPickKeyboard,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import { useDiagramStore } from '@/stores'

const props = defineProps<{
  disabled?: boolean
}>()

const open = ref(false)
const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const bus = useEventBus('MobileLearningSheetButton')
const {
  isPickActive,
  blankCount,
  isLearningSheetActive,
  isFloatBarOpen,
  activatePick,
  dismissFloatBar,
  startRandomLearningSheet,
  exitLearningSheet,
} = useLearningSheetCustomMode()

useLearningSheetPickKeyboard()

bus.on('diagram:loaded', () => {
  restoreLearningSheetUiFromDiagram()
})

onMounted(() => {
  restoreLearningSheetUiFromDiagram()
})

onUnmounted(() => {
  resetLearningSheetCustomModeUi()
})

function openChooser(): void {
  if (props.disabled) return
  if (!diagramStore.data?.nodes?.length) {
    notify.warningKey('canvas.toolbar.createDiagramFirst')
    return
  }
  open.value = true
}

function handleRandom(): void {
  const keepAnswers = diagramStore.learningSheetShowAnswers
  startRandomLearningSheet()
  diagramStore.setLearningSheetShowAnswers(keepAnswers)
  open.value = false
}

function handleCustomPick(): void {
  const keepAnswers = diagramStore.learningSheetShowAnswers
  activatePick()
  diagramStore.setLearningSheetShowAnswers(keepAnswers)
  open.value = false
}

function onKeepAnswersChange(event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  diagramStore.setLearningSheetShowAnswers(checked)
}

function onHideAnswersChange(event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  diagramStore.setLearningSheetShowAnswers(!checked)
}

function handleRestore(): void {
  exitLearningSheet()
  open.value = false
}
</script>

<template>
  <button
    type="button"
    class="bottom-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40"
    :class="
      isLearningSheetActive
        ? 'bg-amber-50 text-amber-800 active:bg-amber-100'
        : 'bg-gray-100 text-gray-700 active:bg-gray-200'
    "
    :disabled="disabled"
    :aria-label="t('canvas.mobile.learningSheet')"
    @click="openChooser"
  >
    <MindMapLearningSheetIcon kind="blanks" />
    <span class="text-xs font-medium"><I18nText k="canvas.mobile.learningSheet" /></span>
  </button>

  <Teleport to="body">
    <div
      v-if="isFloatBarOpen"
      class="mobile-ls-session"
      role="status"
    >
      <p class="mobile-ls-session__title">
        <I18nText
          v-if="isPickActive"
          k="canvas.mindMapSideToolbar.learningSheetPickTitle"
        /><I18nText
          v-else
          k="canvas.mindMapSideToolbar.learningSheetRandomTitle"
        />
      </p>
      <p class="mobile-ls-session__hint">
        <I18nText
          v-if="isPickActive"
          k="canvas.mindMapSideToolbar.learningSheetPickActiveInPanel"
        /><I18nText
          v-else
          k="canvas.mindMapSideToolbar.learningSheetActiveStatus"
          :params="{ count: blankCount }"
        />
      </p>
      <div class="mobile-ls-session__actions">
        <label
          v-if="blankCount > 0"
          class="mobile-ls-session__check"
        >
          <input
            type="checkbox"
            :checked="!diagramStore.learningSheetShowAnswers"
            @change="onHideAnswersChange"
          />
          <span><I18nText k="canvas.mindMapSideToolbar.learningSheetHideAnswers" /></span>
        </label>
        <button
          type="button"
          class="mobile-ls-session__btn"
          @click="dismissFloatBar"
        >
          <I18nText k="canvas.mindMapSideToolbar.learningSheetPickDone" />
        </button>
        <button
          type="button"
          class="mobile-ls-session__btn mobile-ls-session__btn--quiet"
          @click="handleRestore"
        >
          <I18nText k="canvas.mindMapSideToolbar.restoreFullDiagram" />
        </button>
      </div>
    </div>

    <Transition name="model-sheet">
      <div
        v-if="open"
        class="model-sheet-overlay"
        @click.self="open = false"
      >
        <div
          class="model-sheet-panel"
          role="dialog"
          :aria-label="t('canvas.mobile.learningSheet')"
        >
          <div class="model-sheet-handle" />
          <div class="px-4 pt-3 pb-1 text-sm font-semibold text-gray-800">
            <I18nText k="canvas.mobile.learningSheet" />
          </div>
          <p class="px-4 pb-2 text-xs leading-relaxed text-gray-500">
            <I18nText k="canvas.mindMapSideToolbar.learningSheetIntro" />
          </p>
          <div class="flex flex-col gap-2 px-3 pb-3">
            <button
              type="button"
              class="mobile-ls-card"
              @click="handleRandom"
            >
              <span class="mobile-ls-card__icon mobile-ls-card__icon--amber">
                <Shuffle
                  :size="16"
                  :stroke-width="2"
                />
              </span>
              <span class="min-w-0 flex-1 text-start">
                <span class="block text-sm font-semibold text-gray-900">
                  <I18nText k="canvas.mindMapSideToolbar.learningSheetRandomTitle" />
                </span>
                <span class="mt-0.5 block text-xs leading-snug text-gray-500">
                  <I18nText k="canvas.mindMapSideToolbar.learningSheetRandomDesc" />
                </span>
              </span>
            </button>
            <button
              type="button"
              class="mobile-ls-card"
              :class="{ 'mobile-ls-card--active': isPickActive }"
              @click="handleCustomPick"
            >
              <span class="mobile-ls-card__icon mobile-ls-card__icon--blue">
                <Hammer
                  :size="16"
                  class="rotate-[-38deg]"
                  :stroke-width="2"
                />
              </span>
              <span class="min-w-0 flex-1 text-start">
                <span class="block text-sm font-semibold text-gray-900">
                  <I18nText k="canvas.mindMapSideToolbar.learningSheetCustomTitle" />
                </span>
                <span class="mt-0.5 block text-xs leading-snug text-gray-500">
                  <I18nText k="canvas.mobile.learningSheetCustomDesc" />
                </span>
              </span>
            </button>
            <label class="mobile-ls-keep">
              <span class="min-w-0 flex-1">
                <span class="block text-sm font-medium text-gray-800">
                  <I18nText k="canvas.mindMapSideToolbar.learningSheetKeepAnswers" />
                </span>
                <span class="mt-0.5 block text-xs leading-snug text-gray-500">
                  <I18nText k="canvas.mindMapSideToolbar.learningSheetKeepAnswersHint" />
                </span>
              </span>
              <input
                type="checkbox"
                class="h-5 w-5 shrink-0"
                :checked="diagramStore.learningSheetShowAnswers"
                @change="onKeepAnswersChange"
              />
            </label>
            <button
              v-if="isLearningSheetActive"
              type="button"
              class="mobile-ls-restore"
              @click="handleRestore"
            >
              <I18nText k="canvas.mindMapSideToolbar.restoreFullDiagram" />
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.mobile-ls-session {
  position: fixed;
  left: 8px;
  right: 8px;
  bottom: calc(3.4rem + env(safe-area-inset-bottom));
  z-index: 30;
  padding: 10px 12px;
  border: 1px solid #e7e5e4;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 8px 24px rgb(28 25 23 / 12%);
}

.mobile-ls-session__title {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: #1c1917;
}

.mobile-ls-session__hint {
  margin: 2px 0 0;
  font-size: 11px;
  line-height: 1.35;
  color: #78716c;
}

.mobile-ls-session__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.mobile-ls-session__check {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  font-size: 13px;
  color: #44403c;
}

.mobile-ls-session__check input {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.mobile-ls-session__btn {
  min-height: 44px;
  padding: 0 12px;
  border: none;
  border-radius: 10px;
  background: #1c1917;
  color: #fafaf9;
  font-size: 13px;
  font-weight: 600;
}

.mobile-ls-session__btn--quiet {
  background: #f5f5f4;
  color: #44403c;
}

.mobile-ls-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 12px;
  border: 1px solid #e7e5e4;
  border-radius: 12px;
  background: #fff;
  text-align: start;
}

.mobile-ls-card:active,
.mobile-ls-card--active {
  border-color: #1c1917;
  background: #fafaf9;
}

.mobile-ls-card__icon {
  display: inline-flex;
  height: 32px;
  width: 32px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #fff;
}

.mobile-ls-card__icon--amber {
  background: #d97706;
}

.mobile-ls-card__icon--blue {
  background: #2563eb;
}

.mobile-ls-keep {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 4px 4px;
}

.mobile-ls-restore {
  min-height: 44px;
  border: none;
  border-radius: 12px;
  background: #f5f5f4;
  color: #44403c;
  font-size: 14px;
  font-weight: 600;
}
</style>
