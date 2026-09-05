<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import TrainingPlayControls from '@/components/training/TrainingPlayControls.vue'
import {
  requestTrainingEnd,
  requestTrainingFree,
  requestTrainingStep,
} from '@/composables/training/trainingCommands'
import { currentMarkStep, markStepCount } from '@/composables/training/trainingMarkSteps'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'

const route = useRoute()
const authStore = useAuthStore()
const training = useTrainingStore()

const visible = computed(() => {
  if (route.path.startsWith('/training/builder')) return false
  if (!training.isActive || !training.snapshot.course_id) return false
  const mine = Number(authStore.user?.id)
  return mine > 0 && Number(training.snapshot.instructor_id) === mine
})

const canPrev = computed(() => {
  const step = training.snapshot.step
  const index = training.snapshot.step_index || 0
  if (index > 0) return true
  return Boolean(step && currentMarkStep(step) > 1)
})

const canNext = computed(() => {
  const step = training.snapshot.step
  const index = training.snapshot.step_index || 0
  const count = training.snapshot.step_count || 0
  if (count && index < count - 1) return true
  return Boolean(step && currentMarkStep(step) < markStepCount(step))
})
</script>

<template>
  <div
    v-if="visible"
    class="instructor-pad"
  >
    <TrainingPlayControls
      :can-prev="canPrev"
      :can-next="canNext"
      :free="training.isFree"
      @prev="requestTrainingStep(-1)"
      @next="requestTrainingStep(1)"
      @stop="requestTrainingEnd"
      @free="requestTrainingFree()"
    />
  </div>
</template>

<style scoped>
.instructor-pad {
  position: fixed;
  right: 1rem;
  bottom: 1rem;
  z-index: 4300;
}
</style>
