<script setup lang="ts">
/**
 * Floating bar during learning-sheet sessions (custom pick or random blank).
 */
import { computed } from 'vue'

import { Hammer, Shuffle, X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { useLearningSheetCustomMode } from '@/composables/mindMap/useLearningSheetCustomMode'
import { useDiagramStore } from '@/stores'

const { t } = useLanguage()
const diagramStore = useDiagramStore()
const { isPickActive, blankCount, isFloatBarOpen, dismissFloatBar } = useLearningSheetCustomMode()

const showBar = computed(() => isFloatBarOpen.value && diagramStore.isLearningSheet)

const showReferenceAnswers = computed(() => diagramStore.learningSheetShowAnswers)

function onHideAnswersChange(event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  diagramStore.setLearningSheetShowAnswers(!checked)
}
</script>

<template>
  <Transition name="ls-float-bar">
    <div
      v-if="showBar"
      class="learning-sheet-float-bar pointer-events-auto absolute left-1/2 top-3 z-30 flex max-w-[min(94vw,560px)] -translate-x-1/2 items-center gap-3 rounded-xl border border-blue-200/80 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm"
      role="status"
    >
      <span
        class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white shadow-sm"
        :class="
          isPickActive
            ? 'bg-gradient-to-b from-blue-500 to-blue-600'
            : 'bg-gradient-to-b from-amber-500 to-amber-600'
        "
        aria-hidden="true"
      >
        <Hammer
          v-if="isPickActive"
          class="h-4 w-4 -rotate-[38deg]"
          :stroke-width="2"
        />
        <Shuffle
          v-else
          class="h-4 w-4"
          :stroke-width="2"
        />
      </span>

      <div class="min-w-0 flex-1">
        <p class="text-xs font-semibold text-slate-800">
          {{
            isPickActive
              ? t('canvas.mindMapSideToolbar.learningSheetPickTitle')
              : t('canvas.mindMapSideToolbar.learningSheetRandomTitle')
          }}
        </p>
        <p class="mt-0.5 text-[11px] leading-snug text-slate-500">
          {{
            isPickActive
              ? t('canvas.mindMapSideToolbar.learningSheetPickHint', { count: blankCount })
              : t('canvas.mindMapSideToolbar.learningSheetRandomActiveHint', {
                  count: blankCount,
                })
          }}
        </p>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <label
          v-if="blankCount > 0"
          class="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-600"
        >
          <input
            type="checkbox"
            class="h-3 w-3 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            :checked="!showReferenceAnswers"
            @change="onHideAnswersChange"
          />
          <span>{{ t('canvas.mindMapSideToolbar.learningSheetHideAnswers') }}</span>
        </label>

        <button
          type="button"
          class="inline-flex shrink-0 items-center justify-center rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700"
          @click="dismissFloatBar"
        >
          {{ t('canvas.mindMapSideToolbar.learningSheetPickDone') }}
        </button>

        <button
          type="button"
          class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          :aria-label="t('canvas.mindMapSideToolbar.learningSheetPickDone')"
          @click="dismissFloatBar"
        >
          <X
            class="h-3.5 w-3.5"
            :stroke-width="2"
          />
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.ls-float-bar-enter-active,
.ls-float-bar-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.ls-float-bar-enter-from,
.ls-float-bar-leave-to {
  opacity: 0;
  transform: translate(-50%, -6px);
}
</style>
