<script setup lang="ts">
/**
 * Floating banner while custom learning-sheet blank pick mode is active.
 */
import { Hammer, X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { useLearningSheetCustomMode } from '@/composables/mindMap/useLearningSheetCustomMode'

const { t } = useLanguage()
const { isPickActive, blankCount, deactivatePick } = useLearningSheetCustomMode()
</script>

<template>
  <Transition name="ls-pick-banner">
    <div
      v-if="isPickActive"
      class="learning-sheet-pick-banner pointer-events-auto absolute left-1/2 top-3 z-30 flex max-w-[min(92vw,520px)] -translate-x-1/2 items-center gap-3 rounded-xl border border-blue-200/80 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm"
      role="status"
    >
      <span
        class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-b from-blue-500 to-blue-600 text-white shadow-sm"
        aria-hidden="true"
      >
        <Hammer
          class="h-4 w-4 -rotate-[38deg]"
          :stroke-width="2"
        />
      </span>

      <div class="min-w-0 flex-1">
        <p class="text-xs font-semibold text-slate-800">
          {{ t('canvas.mindMapSideToolbar.learningSheetPickTitle') }}
        </p>
        <p class="mt-0.5 text-[11px] leading-snug text-slate-500">
          {{
            t('canvas.mindMapSideToolbar.learningSheetPickHint', {
              count: blankCount,
            })
          }}
        </p>
      </div>

      <button
        type="button"
        class="inline-flex shrink-0 items-center justify-center rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700"
        @click="deactivatePick"
      >
        {{ t('canvas.mindMapSideToolbar.learningSheetPickDone') }}
      </button>

      <button
        type="button"
        class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
        :aria-label="t('canvas.mindMapSideToolbar.learningSheetPickDone')"
        @click="deactivatePick"
      >
        <X
          class="h-3.5 w-3.5"
          :stroke-width="2"
        />
      </button>
    </div>
  </Transition>
</template>

<style scoped>
.ls-pick-banner-enter-active,
.ls-pick-banner-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.ls-pick-banner-enter-from,
.ls-pick-banner-leave-to {
  opacity: 0;
  transform: translate(-50%, -6px);
}
</style>
