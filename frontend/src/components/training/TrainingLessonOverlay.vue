<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import TrainingStepMarks from '@/components/training/TrainingStepMarks.vue'
import { visibleMarkOverlays } from '@/composables/training/trainingMarkSteps'
import { useTrainingStore } from '@/stores/training'
import type { TrainingCourseStep } from '@/types/training'
import { shouldSkipTrainingFollow } from '@/utils/trainingClient'

const route = useRoute()
const training = useTrainingStore()
const frozen = ref<TrainingCourseStep | null>(null)

const isMedia = (step: TrainingCourseStep | null | undefined): boolean =>
  step?.type === 'slide' || step?.type === 'video'

watch(
  () => [training.isLive, training.isActive, training.snapshot.step] as const,
  ([live, active, step]) => {
    if (!active || !live) {
      frozen.value = null
      return
    }
    if (isMedia(step) && step?.asset_url) {
      frozen.value = step
      return
    }
    frozen.value = null
  },
  { immediate: true }
)

const visible = computed(() => {
  if (shouldSkipTrainingFollow()) return false
  if (route.path.startsWith('/training')) return false
  return Boolean(frozen.value)
})
const marks = computed(() => (frozen.value ? visibleMarkOverlays(frozen.value) : []))
</script>

<template>
  <div
    v-if="visible && frozen"
    class="lesson-overlay"
  >
    <img
      v-if="frozen.type === 'slide' && frozen.asset_url"
      class="lesson-overlay__media"
      :src="frozen.asset_url"
      alt=""
    >
    <video
      v-else-if="frozen.type === 'video' && frozen.asset_url"
      class="lesson-overlay__media"
      :src="frozen.asset_url"
      controls
    />
    <TrainingStepMarks
      :overlays="marks"
      :step="frozen"
    />
  </div>
</template>

<style scoped>
.lesson-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: #111827;
}
.lesson-overlay__media {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
</style>
