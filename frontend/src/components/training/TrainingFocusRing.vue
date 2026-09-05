<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'

import { queryTrainingFocus } from '@/composables/training/applyTrainingUiTarget'
import { useTrainingStore } from '@/stores/training'

const training = useTrainingStore()
const box = ref<{ top: number; left: number; width: number; height: number } | null>(null)
let frame = 0

function measure(): void {
  const el = queryTrainingFocus(training.uiFocusKey)
  if (!el) {
    box.value = null
    return
  }
  const rect = el.getBoundingClientRect()
  box.value = {
    top: rect.top - 6,
    left: rect.left - 6,
    width: rect.width + 12,
    height: rect.height + 12,
  }
}

function tick(): void {
  measure()
  if (training.uiFocusKey) {
    frame = window.requestAnimationFrame(tick)
  }
}

watch(
  () => training.uiFocusKey,
  (key) => {
    window.cancelAnimationFrame(frame)
    if (!key) {
      box.value = null
      return
    }
    frame = window.requestAnimationFrame(tick)
  },
  { immediate: true }
)

onUnmounted(() => {
  window.cancelAnimationFrame(frame)
})
</script>

<template>
  <div
    v-if="box"
    class="training-focus"
    :style="{
      top: `${box.top}px`,
      left: `${box.left}px`,
      width: `${box.width}px`,
      height: `${box.height}px`,
    }"
  />
</template>

<style scoped>
.training-focus {
  position: fixed;
  z-index: 4100;
  border: 2px solid #e30613;
  box-shadow: 0 0 0 4px rgb(227 6 19 / 0.18);
  pointer-events: none;
}
</style>
