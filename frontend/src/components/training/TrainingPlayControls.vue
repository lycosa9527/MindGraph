<script setup lang="ts">
import { useLanguage } from '@/composables'

defineProps<{
  canPrev?: boolean
  canNext?: boolean
  free?: boolean
  busy?: boolean
  showFree?: boolean
}>()

const emit = defineEmits<{
  prev: []
  next: []
  stop: []
  free: []
}>()

const { t } = useLanguage()
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
    <button
      v-if="showFree !== false"
      type="button"
      class="play-pad__btn play-pad__btn--free"
      :class="{ 'is-on': free }"
      :disabled="busy"
      :title="t('training.freeHint')"
      @click="emit('free')"
    >
      {{ t('training.free') }}
    </button>
  </div>
</template>

<style scoped>
.play-pad {
  display: grid;
  width: 7.5rem;
  gap: 0.55rem;
}
.play-pad__btn {
  min-height: 3.4rem;
  border: 0;
  background: #1c1917;
  color: #fafaf9;
  font-size: 1.15rem;
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
.play-pad__btn--free {
  background: #0f766e;
}
.play-pad__btn--free:hover:not(:disabled) {
  background: #0d9488;
}
.play-pad__btn--free.is-on {
  box-shadow: inset 0 0 0 3px #ccfbf1;
}
</style>
