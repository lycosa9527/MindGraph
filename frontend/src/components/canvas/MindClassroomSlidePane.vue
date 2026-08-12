<script setup lang="ts">
/**
 * Right-pane slide lecture player for 幻灯片讲解 (fullscreen dual-pane).
 */
import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import { ChevronLeft, ChevronRight, Pause, Play, Square, Volume2, VolumeX, X } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useMindClassroomLecture } from '@/composables/mindMap/useMindClassroomLecture'
import { useMindClassroomStore } from '@/stores'

const { t } = useLanguage()
const classroomStore = useMindClassroomStore()
const {
  status,
  currentStep,
  stepIndex,
  stepCount,
  canGoPrev,
  voiceEnabled,
  transitioning,
  slideStyle,
} = storeToRefs(classroomStore)

const { togglePause, nextStep, prevStep, stopLecture, setVoiceEnabled } = useMindClassroomLecture()

const isPaused = computed(() => status.value === 'paused')

const kindLabel = computed(() => {
  const kind = currentStep.value?.kind
  if (kind === 'overview') return t('canvas.mindClassroom.slide.kindOverview')
  if (kind === 'closing') return t('canvas.mindClassroom.slide.kindClosing')
  return t('canvas.mindClassroom.slide.kindBranch')
})

const styleTitle = computed(() =>
  t(`canvas.mindClassroom.settings.slideStyle.${slideStyle.value}.title`)
)
</script>

<template>
  <aside
    class="mc-slide-pane"
    :aria-label="t('canvas.mindClassroom.settings.presentation.slide_deck.title')"
  >
    <header class="mc-slide-pane__header">
      <div class="mc-slide-pane__header-left">
        <button
          type="button"
          class="mc-slide-pane__icon-btn"
          :aria-label="t('canvas.mindClassroom.lecture.stop')"
          :title="t('canvas.mindClassroom.lecture.stop')"
          @click="stopLecture()"
        >
          <X
            class="h-4 w-4"
            :stroke-width="2.25"
          />
        </button>
        <div class="min-w-0">
          <p class="mc-slide-pane__kicker">
            {{ t('canvas.mindClassroom.settings.presentation.slide_deck.title') }}
            · {{ styleTitle }}
          </p>
          <p class="mc-slide-pane__heading truncate">
            {{ currentStep?.title }}
          </p>
        </div>
      </div>
      <span class="mc-slide-pane__page"> {{ stepIndex + 1 }} / {{ stepCount }} </span>
    </header>

    <div class="mc-slide-pane__stage">
      <button
        type="button"
        class="mc-slide-pane__nav mc-slide-pane__nav--prev"
        :disabled="!canGoPrev || transitioning"
        :aria-label="t('canvas.mindClassroom.lecture.prev')"
        @click="prevStep()"
      >
        <ChevronLeft class="h-6 w-6" />
      </button>

      <div
        class="mc-slide-card"
        :class="`mc-slide-card--${slideStyle}`"
        aria-live="polite"
        aria-atomic="true"
      >
        <span class="mc-slide-card__kind">{{ kindLabel }}</span>
        <h2 class="mc-slide-card__title">
          {{ currentStep?.title }}
        </h2>
        <ul
          v-if="currentStep?.bullets?.length"
          class="mc-slide-card__bullets"
        >
          <li
            v-for="(line, i) in currentStep.bullets"
            :key="`${currentStep.id}-${i}`"
          >
            {{ line }}
          </li>
        </ul>
        <div class="mc-slide-card__caption">
          {{ currentStep?.caption }}
        </div>
      </div>

      <button
        type="button"
        class="mc-slide-pane__nav mc-slide-pane__nav--next"
        :disabled="transitioning"
        :aria-label="t('canvas.mindClassroom.lecture.next')"
        @click="nextStep()"
      >
        <ChevronRight class="h-6 w-6" />
      </button>
    </div>

    <div class="mc-slide-pane__dock">
      <button
        type="button"
        class="mc-dock-btn"
        :aria-label="
          voiceEnabled
            ? t('canvas.mindClassroom.lecture.mute')
            : t('canvas.mindClassroom.lecture.unmute')
        "
        @click="setVoiceEnabled(!voiceEnabled)"
      >
        <Volume2
          v-if="voiceEnabled"
          class="h-4 w-4"
        />
        <VolumeX
          v-else
          class="h-4 w-4"
        />
      </button>

      <button
        type="button"
        class="mc-dock-btn"
        :disabled="!canGoPrev || transitioning"
        :aria-label="t('canvas.mindClassroom.lecture.prev')"
        @click="prevStep()"
      >
        <ChevronLeft class="h-4 w-4" />
      </button>

      <button
        type="button"
        class="mc-dock-btn mc-dock-btn--primary"
        :aria-label="
          isPaused
            ? t('canvas.mindClassroom.lecture.resume')
            : t('canvas.mindClassroom.lecture.pause')
        "
        @click="togglePause()"
      >
        <Play
          v-if="isPaused"
          class="h-4 w-4"
        />
        <Pause
          v-else
          class="h-4 w-4"
        />
      </button>

      <button
        type="button"
        class="mc-dock-btn"
        :disabled="transitioning"
        :aria-label="t('canvas.mindClassroom.lecture.next')"
        @click="nextStep()"
      >
        <ChevronRight class="h-4 w-4" />
      </button>

      <button
        type="button"
        class="mc-dock-btn mc-dock-btn--stop"
        :aria-label="t('canvas.mindClassroom.lecture.stop')"
        @click="stopLecture()"
      >
        <Square class="h-3.5 w-3.5" />
      </button>
    </div>
  </aside>
</template>

<style scoped>
.mc-slide-pane {
  display: flex;
  flex-direction: column;
  width: min(50vw, 640px);
  min-width: min(360px, 50vw);
  flex-shrink: 0;
  height: 100%;
  border-left: 1px solid #e2e8f0;
  background: #0f172a0a;
}

.mc-slide-pane__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
}

.mc-slide-pane__header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.mc-slide-pane__icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 999px;
  color: #475569;
  background: #f1f5f9;
  cursor: pointer;
  flex-shrink: 0;
}

.mc-slide-pane__icon-btn:hover {
  background: #e2e8f0;
}

.mc-slide-pane__kicker {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  color: #0ea5e9;
}

.mc-slide-pane__heading {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.mc-slide-pane__page {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: #e2e8f0;
  font-size: 11px;
  font-weight: 700;
  color: #475569;
}

.mc-slide-pane__stage {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 44px 12px;
}

.mc-slide-pane__nav {
  position: absolute;
  top: 50%;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 999px;
  color: #fff;
  background: rgb(15 23 42 / 0.35);
  transform: translateY(-50%);
  cursor: pointer;
}

.mc-slide-pane__nav:hover:not(:disabled) {
  background: rgb(15 23 42 / 0.5);
}

.mc-slide-pane__nav:disabled {
  opacity: 0.25;
  cursor: not-allowed;
}

.mc-slide-pane__nav--prev {
  left: 8px;
}

.mc-slide-pane__nav--next {
  right: 8px;
}

.mc-slide-card {
  position: relative;
  width: 100%;
  height: min(100%, 560px);
  display: flex;
  flex-direction: column;
  padding: 28px 24px 20px;
  border-radius: 18px;
  box-shadow:
    0 20px 40px rgb(15 23 42 / 0.18),
    0 2px 8px rgb(15 23 42 / 0.08);
  overflow: hidden;
}

.mc-slide-card__kind {
  align-self: flex-start;
  margin-bottom: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.mc-slide-card__title {
  margin: 0 0 14px;
  font-size: clamp(22px, 2.6vw, 32px);
  font-weight: 800;
  line-height: 1.25;
}

.mc-slide-card__bullets {
  margin: 0;
  padding: 0 0 0 1.1em;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 15px;
  line-height: 1.45;
  overflow: auto;
  flex: 1;
  min-height: 0;
}

.mc-slide-card__caption {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 12px;
  line-height: 1.5;
  max-height: 5.4em;
  overflow: hidden;
}

/* —— Style presets —— */
.mc-slide-card--general {
  color: #1e3a5f;
  background: linear-gradient(180deg, #fcfcfd 0%, #f1f5f9 100%);
  border: 1px solid #cbd5e1;
}

.mc-slide-card--general .mc-slide-card__kind {
  color: #1d4ed8;
  background: #dbeafe;
}

.mc-slide-card--general .mc-slide-card__caption {
  background: rgb(37 99 235 / 0.08);
  color: #334155;
}

.mc-slide-card--chalkboard {
  color: #f8fafc;
  background:
    radial-gradient(circle at 18% 22%, rgb(255 255 255 / 0.06), transparent 42%),
    linear-gradient(160deg, #1f2937 0%, #111827 100%);
  border: 1px solid #334155;
}

.mc-slide-card--chalkboard .mc-slide-card__kind {
  color: #fde68a;
  background: rgb(253 224 71 / 0.15);
}

.mc-slide-card--chalkboard .mc-slide-card__caption {
  background: rgb(0 0 0 / 0.35);
  color: #e2e8f0;
}

.mc-slide-card--comic {
  color: #1e1b4b;
  background:
    radial-gradient(circle at 12% 18%, rgb(254 240 138 / 0.85), transparent 36%),
    radial-gradient(circle at 88% 22%, rgb(244 114 182 / 0.35), transparent 40%),
    linear-gradient(145deg, #fff7ed 0%, #fce7f3 55%, #e0e7ff 100%);
  border: 2px solid #1e1b4b;
  box-shadow: 4px 4px 0 #1e1b4b;
}

.mc-slide-card--comic .mc-slide-card__kind {
  color: #fff;
  background: #7c3aed;
  border: 1.5px solid #1e1b4b;
}

.mc-slide-card--comic .mc-slide-card__caption {
  background: #fff;
  border: 1.5px solid #1e1b4b;
  color: #312e81;
}

.mc-slide-card--handdrawn {
  color: #7c2d12;
  background-color: #fffbeb;
  background-image:
    radial-gradient(circle at 18% 28%, rgb(120 53 15 / 0.1) 1.2px, transparent 1.6px),
    radial-gradient(circle at 72% 64%, rgb(120 53 15 / 0.08) 1px, transparent 1.4px),
    linear-gradient(180deg, #fff7ed 0%, #ffedd5 100%);
  background-size:
    12px 12px,
    16px 16px,
    auto;
  border: 1.5px dashed #c2410c;
}

.mc-slide-card--handdrawn .mc-slide-card__kind {
  color: #9a3412;
  background: #ffedd5;
  border: 1px dashed #ea580c;
}

.mc-slide-card--handdrawn .mc-slide-card__caption {
  background: rgb(255 255 255 / 0.72);
  border: 1px dashed #fdba74;
  color: #7c2d12;
}

.mc-slide-pane__dock {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 0 16px 16px;
  padding: 8px 12px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 8px 24px rgb(15 23 42 / 0.08);
}

.mc-dock-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 999px;
  color: #475569;
  background: transparent;
  cursor: pointer;
}

.mc-dock-btn:hover:not(:disabled) {
  background: #f1f5f9;
}

.mc-dock-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.mc-dock-btn--primary {
  width: 42px;
  height: 42px;
  color: #fff;
  background: linear-gradient(180deg, #38bdf8 0%, #2563eb 100%);
}

.mc-dock-btn--primary:hover:not(:disabled) {
  color: #fff;
  background: linear-gradient(180deg, #0ea5e9 0%, #1d4ed8 100%);
}

.mc-dock-btn--stop {
  color: #b91c1c;
}

.mc-dock-btn--stop:hover:not(:disabled) {
  background: #fef2f2;
}

@media (max-width: 768px) {
  .mc-slide-pane {
    width: 100%;
    min-width: 0;
    border-left: none;
  }

  .mc-slide-pane__stage {
    padding-inline: 38px;
  }
}
</style>
