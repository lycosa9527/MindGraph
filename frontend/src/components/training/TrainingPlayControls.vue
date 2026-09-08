<script setup lang="ts">
import { computed } from 'vue'

import { useLanguage } from '@/composables'
import type { TrainingSteerMode } from '@/composables/training/applyTrainingSnapshot'

const props = withDefaults(
  defineProps<{
    canPrev?: boolean
    canNext?: boolean
    mode?: TrainingSteerMode
    busy?: boolean
    showMode?: boolean
    layout?: 'pad' | 'stack'
  }>(),
  {
    canPrev: false,
    canNext: false,
    mode: 'pull',
    busy: false,
    showMode: true,
    layout: 'pad',
  }
)

const emit = defineEmits<{
  prev: []
  next: []
  stop: []
  mode: [value: TrainingSteerMode]
}>()

const { t } = useLanguage()
const currentMode = computed<TrainingSteerMode>(() => props.mode)
const showSteer = computed(() => props.showMode)

function pickMode(next: TrainingSteerMode): void {
  if (next === currentMode.value) return
  emit('mode', next)
}
</script>

<template>
  <div
    class="play-pad"
    :class="{ 'play-pad--stack': layout === 'stack' }"
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
  width: min(16.75rem, calc(100vw - 2rem));
  grid-template-columns: 1fr 1fr 1fr;
  overflow: hidden;
  border: 1px solid #a8a29e;
  background: #1c1917;
  box-shadow: 0 8px 28px rgb(0 0 0 / 0.4);
}
.play-pad__btn {
  min-height: 2.6rem;
  border: 0;
  border-right: 1px solid #57534e;
  background: #1c1917;
  color: #fafaf9;
  font-size: 0.95rem;
  font-weight: 750;
  letter-spacing: 0.04em;
  cursor: pointer;
}
.play-pad__btn:last-of-type {
  border-right: 0;
}
.play-pad__btn:hover:not(:disabled) {
  background: #44403c;
}
.play-pad__btn:disabled {
  background: #d6d3d1;
  color: #78716c;
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
  grid-column: 1 / -1;
  grid-template-columns: 1fr 1fr;
  min-height: 2.4rem;
  border-top: 1px solid #78716c;
  background: #292524;
}
.play-pad__seg {
  border: 0;
  border-right: 1px solid #57534e;
  background: transparent;
  color: #a8a29e;
  font-size: 0.92rem;
  font-weight: 750;
  letter-spacing: 0.03em;
  cursor: pointer;
}
.play-pad__seg:last-child {
  border-right: 0;
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
.play-pad--stack {
  width: 100%;
  min-height: 0;
  grid-template-columns: 1fr;
}
.play-pad--stack .play-pad__btn {
  min-height: 44px;
  border-right: 0;
  border-bottom: 1px solid #57534e;
}
.play-pad--stack .play-pad__mode {
  grid-column: auto;
  min-height: 44px;
}
</style>
