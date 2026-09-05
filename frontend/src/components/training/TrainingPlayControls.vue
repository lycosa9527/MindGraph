<script setup lang="ts">
import { computed } from 'vue'

import { useLanguage } from '@/composables'
import type { TrainingSteerMode } from '@/composables/training/applyTrainingSnapshot'

const props = defineProps<{
  canPrev?: boolean
  canNext?: boolean
  mode?: TrainingSteerMode
  busy?: boolean
  showMode?: boolean
}>()

const emit = defineEmits<{
  prev: []
  next: []
  stop: []
  mode: [value: TrainingSteerMode]
}>()

const { t } = useLanguage()
const currentMode = computed<TrainingSteerMode>(() => props.mode ?? 'pull')
const showSteer = computed(() => props.showMode !== false)

function pickMode(next: TrainingSteerMode): void {
  emit('mode', next)
}
</script>

<template>
  <div
    class="play-pad"
    role="group"
    :aria-label="t('training.playPad')"
  >
    <button
      type="button"
      class="play-pad__btn"
      :disabled="busy || !canPrev"
      @click="emit('prev')"
    >
      {{ t('training.prevStep') }}
    </button>
    <button
      type="button"
      class="play-pad__btn"
      :disabled="busy || !canNext"
      @click="emit('next')"
    >
      {{ t('training.nextStep') }}
    </button>
    <button
      type="button"
      class="play-pad__btn play-pad__btn--stop"
      :disabled="busy"
      @click="emit('stop')"
    >
      {{ t('training.stop') }}
    </button>
    <div
      v-if="showSteer"
      class="play-pad__mode"
      role="radiogroup"
      :aria-label="t('training.modeGroup')"
    >
      <button
        type="button"
        role="radio"
        class="play-pad__seg"
        :class="{ 'is-on': currentMode === 'free' }"
        :aria-checked="currentMode === 'free'"
        :disabled="busy"
        :title="t('training.freeHint')"
        @click="pickMode('free')"
      >
        {{ t('training.free') }}
      </button>
      <button
        type="button"
        role="radio"
        class="play-pad__seg"
        :class="{ 'is-on': currentMode === 'pull' }"
        :aria-checked="currentMode === 'pull'"
        :disabled="busy"
        :title="t('training.pullHint')"
        @click="pickMode('pull')"
      >
        {{ t('training.pull') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.play-pad {
  display: grid;
  width: 9.5rem;
  gap: 0.45rem;
}
@media (max-height: 780px) {
  .play-pad {
    width: min(16.5rem, calc(100vw - 2rem));
    grid-template-columns: 1fr 1fr 1fr;
  }
  .play-pad__mode {
    grid-column: 1 / -1;
  }
}
.play-pad__btn {
  min-height: 2.8rem;
  border: 0;
  background: #1c1917;
  color: #fafaf9;
  font-size: 1.05rem;
  font-weight: 750;
  letter-spacing: 0.04em;
  cursor: pointer;
}
.play-pad__btn:hover:not(:disabled) {
  background: #44403c;
}
.play-pad__btn:disabled {
  background: #d6d3d1;
  color: #a8a29e;
  cursor: default;
}
.play-pad__btn--stop {
  background: #dc2626;
}
.play-pad__btn--stop:hover:not(:disabled) {
  background: #b91c1c;
}
.play-pad__mode {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 2.6rem;
  overflow: hidden;
  background: #292524;
}
.play-pad__seg {
  border: 0;
  background: transparent;
  color: #a8a29e;
  font-size: 0.92rem;
  font-weight: 750;
  letter-spacing: 0.03em;
  cursor: pointer;
}
.play-pad__seg:hover:not(:disabled):not(.is-on) {
  color: #fafaf9;
}
.play-pad__seg.is-on {
  background: #0f766e;
  color: #fafaf9;
}
.play-pad__seg.is-on:nth-child(2) {
  background: #1d4ed8;
}
.play-pad__seg:disabled {
  color: #78716c;
  cursor: default;
}
</style>
