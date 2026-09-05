<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import TrainingPlayControls from '@/components/training/TrainingPlayControls.vue'
import { useLanguage, useNotifications } from '@/composables'
import { currentMarkStep, markStepCount } from '@/composables/training/trainingMarkSteps'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'
import { endTraining, freeTraining, stepTrainingCourse } from '@/utils/trainingApi'

const { t } = useLanguage()
const notify = useNotifications()
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

async function steer(work: () => Promise<void>): Promise<void> {
  try {
    await work()
  } catch {
    notify.error(t('training.steerFailed'))
  }
}

async function move(delta: number): Promise<void> {
  const sessionId = training.snapshot.session_id
  const orgId = training.snapshot.org_id
  if (!sessionId || orgId == null) return
  await steer(async () => {
    training.applySnapshot(await stepTrainingCourse(sessionId, orgId, { delta }))
  })
}

async function stop(): Promise<void> {
  const sessionId = training.snapshot.session_id
  const orgId = training.snapshot.org_id
  if (!sessionId || orgId == null) return
  await steer(async () => {
    training.applySnapshot(await endTraining(sessionId, orgId))
  })
}

async function toggleFree(): Promise<void> {
  const sessionId = training.snapshot.session_id
  const orgId = training.snapshot.org_id
  if (!sessionId || orgId == null) return
  await steer(async () => {
    training.applySnapshot(await freeTraining(sessionId, orgId, !training.isFree))
  })
}
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
      @prev="move(-1)"
      @next="move(1)"
      @stop="stop"
      @free="toggleFree"
    />
  </div>
</template>

<style scoped>
.instructor-pad {
  position: fixed;
  right: 1rem;
  bottom: 1rem;
  z-index: 38;
}
</style>
