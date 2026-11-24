<script setup lang="ts">
/**
 * Setup chooser before drag practice. Same glass dialog as 挖空支架图.
 */
import { GripHorizontal, Hammer, LayoutList, Shuffle } from '@lucide/vue'

import AiGenerateGlassHero from '@/components/canvas/AiGenerateGlassHero.vue'
import I18nText from '@/components/common/I18nText.vue'
import {
  closeDragPracticeSetup,
  dragPracticeSetupOpen,
  startDragPracticeFromCustomPick,
  startDragPracticeFromFullBlank,
  startDragPracticeFromRandom,
} from '@/composables/mindMap/useDragPractice'
</script>

<template>
  <Teleport to="body">
    <div
      v-if="dragPracticeSetupOpen"
      class="mm-canvas-center-modal"
      role="presentation"
      @click.self="closeDragPracticeSetup()"
    >
      <aside
        class="mind-map-side-rail-panel mind-map-side-panel learning-sheet-glass-panel pointer-events-auto ai-gen-shell ai-gen-shell--learningSheet"
        :aria-label="$t('canvas.dragPractice.title')"
      >
        <AiGenerateGlassHero
          :icon="GripHorizontal"
          :badge="GripHorizontal"
          title-key="canvas.dragPractice.title"
          line1-key="canvas.dragPractice.setupHint"
          @close="closeDragPracticeSetup()"
        />

        <div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
          <div class="flex flex-col gap-3 px-4 py-5">
            <button
              type="button"
              class="learning-sheet-mode-card"
              @click="startDragPracticeFromFullBlank()"
            >
              <span class="learning-sheet-mode-card__icon learning-sheet-mode-card__icon--violet">
                <LayoutList
                  class="h-4 w-4"
                  :stroke-width="2"
                />
              </span>
              <span class="min-w-0 flex-1 text-left">
                <span class="block text-sm font-semibold text-slate-800">
                  <I18nText k="canvas.dragPractice.fullBlankTitle" />
                </span>
                <span class="mt-0.5 block text-[11px] leading-snug text-slate-500">
                  <I18nText k="canvas.dragPractice.fullBlankDesc" />
                </span>
              </span>
            </button>

            <button
              type="button"
              class="learning-sheet-mode-card"
              @click="startDragPracticeFromRandom()"
            >
              <span class="learning-sheet-mode-card__icon learning-sheet-mode-card__icon--amber">
                <Shuffle
                  class="h-4 w-4"
                  :stroke-width="2"
                />
              </span>
              <span class="min-w-0 flex-1 text-left">
                <span class="block text-sm font-semibold text-slate-800">
                  <I18nText k="canvas.dragPractice.randomTitle" />
                </span>
                <span class="mt-0.5 block text-[11px] leading-snug text-slate-500">
                  <I18nText k="canvas.dragPractice.randomDesc" />
                </span>
              </span>
            </button>

            <button
              type="button"
              class="learning-sheet-mode-card"
              @click="startDragPracticeFromCustomPick()"
            >
              <span class="learning-sheet-mode-card__icon learning-sheet-mode-card__icon--blue">
                <Hammer
                  class="h-4 w-4 rotate-[-38deg]"
                  :stroke-width="2"
                />
              </span>
              <span class="min-w-0 flex-1 text-left">
                <span class="block text-sm font-semibold text-slate-800">
                  <I18nText k="canvas.dragPractice.customTitle" />
                </span>
                <span class="mt-0.5 block text-[11px] leading-snug text-slate-500">
                  <I18nText k="canvas.dragPractice.customDesc" />
                </span>
              </span>
            </button>
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

.learning-sheet-mode-card__icon--violet {
  color: var(--swiss-geek-violet-ui, #6d28d9);
  background: var(--swiss-geek-violet-soft, #f5f3ff);
  border-color: color-mix(
    in srgb,
    var(--swiss-geek-violet-ui, #6d28d9) 22%,
    var(--swiss-border, #e7e5e4)
  );
}

.learning-sheet-mode-card__icon--amber {
  color: var(--swiss-geek-amber-ui, #b45309);
  background: var(--swiss-geek-amber-soft, #fffbeb);
  border-color: color-mix(
    in srgb,
    var(--swiss-geek-amber-ui, #b45309) 22%,
    var(--swiss-border, #e7e5e4)
  );
}

.learning-sheet-mode-card__icon--blue {
  color: var(--swiss-geek-cyan-ui, #0e7490);
  background: var(--swiss-geek-cyan-soft, #ecfeff);
  border-color: color-mix(
    in srgb,
    var(--swiss-geek-cyan-ui, #0e7490) 22%,
    var(--swiss-border, #e7e5e4)
  );
}
</style>
