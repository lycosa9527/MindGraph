<script setup lang="ts">
/**
 * Live Mind Classroom HUD — caption + transport controls.
 */
import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import { ChevronLeft, ChevronRight, Pause, Play, Square, Volume2, VolumeX } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useMindClassroomLecture } from '@/composables/mindMap/useMindClassroomLecture'
import { PRESENTATION_Z } from '@/config/uiConfig'
import { useMindClassroomStore } from '@/stores'

const { t } = useLanguage()
const classroomStore = useMindClassroomStore()
const {
  status,
  currentStep,
  stepIndex,
  stepCount,
  canGoPrev,
  progress,
  voiceEnabled,
  transitioning,
} = storeToRefs(classroomStore)

const { togglePause, nextStep, prevStep, stopLecture, setVoiceEnabled } = useMindClassroomLecture()

const regionLabel = computed(() => {
  const title = currentStep.value?.title ?? ''
  return `${title} · ${stepIndex.value + 1} / ${stepCount.value}`
})

const progressPercent = computed(() => Math.round(progress.value * 100))

const isPaused = computed(() => status.value === 'paused')
</script>

<template>
  <div
    class="mc-lecture-overlay"
    :style="{ zIndex: PRESENTATION_Z.TIMER_OVERLAY - 1 }"
    role="region"
    :aria-label="regionLabel"
  >
    <div class="mc-lecture-overlay__caption">
      <div class="mc-lecture-overlay__meta">
        <span class="mc-lecture-overlay__badge">
          {{ t('canvas.mindClassroom.title') }}
        </span>
        <span class="mc-lecture-overlay__counter"> {{ stepIndex + 1 }} / {{ stepCount }} </span>
      </div>
      <p class="mc-lecture-overlay__title">
        {{ currentStep?.title }}
      </p>
      <p
        class="mc-lecture-overlay__text"
        aria-live="polite"
      >
        {{ currentStep?.caption }}
      </p>
      <div
        class="mc-lecture-overlay__progress"
        role="progressbar"
        :aria-label="t('canvas.mindClassroom.title')"
        :aria-valuenow="progressPercent"
        aria-valuemin="0"
        aria-valuemax="100"
      >
        <span
          class="mc-lecture-overlay__progress-fill"
          :style="{ width: `${progressPercent}%` }"
        />
      </div>
    </div>

    <div class="mc-lecture-overlay__controls">
      <button
        type="button"
        class="mc-ctrl"
        :aria-label="
          voiceEnabled
            ? t('canvas.mindClassroom.lecture.mute')
            : t('canvas.mindClassroom.lecture.unmute')
        "
        :title="
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
        class="mc-ctrl"
        :disabled="!canGoPrev || transitioning"
        :aria-label="t('canvas.mindClassroom.lecture.prev')"
        @click="prevStep()"
      >
        <ChevronLeft class="h-4 w-4" />
      </button>

      <button
        type="button"
        class="mc-ctrl mc-ctrl--primary"
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
        class="mc-ctrl"
        :disabled="transitioning"
        :aria-label="t('canvas.mindClassroom.lecture.next')"
        @click="nextStep()"
      >
        <ChevronRight class="h-4 w-4" />
      </button>

      <button
        type="button"
        class="mc-ctrl mc-ctrl--stop"
        :aria-label="t('canvas.mindClassroom.lecture.stop')"
        :title="t('canvas.mindClassroom.lecture.stop')"
        @click="stopLecture()"
      >
        <Square class="h-3.5 w-3.5" />
        <span>{{ t('canvas.mindClassroom.lecture.stop') }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.mc-lecture-overlay {
  position: fixed;
  left: 50%;
  bottom: 20px;
  transform: translateX(-50%);
  width: min(560px, calc(100vw - 32px));
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: auto;
}

.mc-lecture-overlay__caption {
  padding: 14px 16px 12px;
  border-radius: 18px;
  border: 1px solid rgb(186 230 253 / 0.95);
  background: rgb(255 255 255 / 0.96);
  box-shadow:
    0 16px 40px rgb(14 165 233 / 0.16),
    0 2px 8px rgb(15 23 42 / 0.06);
  backdrop-filter: blur(12px);
}

.mc-lecture-overlay__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.mc-lecture-overlay__badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0e7490;
  font-size: 11px;
  font-weight: 700;
}

.mc-lecture-overlay__counter {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
}

.mc-lecture-overlay__title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.mc-lecture-overlay__text {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: #334155;
  max-height: 4.8em;
  overflow: hidden;
}

.mc-lecture-overlay__progress {
  margin-top: 10px;
  height: 3px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.mc-lecture-overlay__progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #22d3ee, #2563eb);
  transition: width 0.25s ease;
}

.mc-lecture-overlay__controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 999px;
  border: 1px solid rgb(226 232 240 / 0.95);
  background: rgb(255 255 255 / 0.94);
  box-shadow: 0 8px 24px rgb(15 23 42 / 0.1);
}

.mc-ctrl {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 36px;
  height: 36px;
  padding: 0 10px;
  border: none;
  border-radius: 999px;
  color: #475569;
  background: transparent;
  cursor: pointer;
}

.mc-ctrl:hover:not(:disabled) {
  background: #f1f5f9;
  color: #0f172a;
}

.mc-ctrl:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.mc-ctrl--primary {
  width: 42px;
  height: 42px;
  color: #fff;
  background: linear-gradient(180deg, #38bdf8 0%, #2563eb 100%);
  box-shadow: 0 4px 12px rgb(37 99 235 / 0.35);
}

.mc-ctrl--primary:hover:not(:disabled) {
  color: #fff;
  background: linear-gradient(180deg, #0ea5e9 0%, #1d4ed8 100%);
}

.mc-ctrl--stop {
  color: #b91c1c;
  font-size: 12px;
  font-weight: 700;
}

.mc-ctrl--stop:hover:not(:disabled) {
  background: #fef2f2;
  color: #991b1b;
}
</style>
