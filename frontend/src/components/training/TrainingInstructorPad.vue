<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import TrainingPlayControls from '@/components/training/TrainingPlayControls.vue'
import {
  trainingSteerMode,
  type TrainingSteerMode,
} from '@/composables/training/applyTrainingSnapshot'
import {
  requestTrainingEnd,
  requestTrainingFree,
  requestTrainingStep,
} from '@/composables/training/trainingCommands'
import { canSteerLiveSnapshot } from '@/composables/training/trainingMarkSteps'
import { useTrainingPadAnchor } from '@/composables/training/useTrainingPadAnchor'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'
import { isTrainingRailVisible, shouldHideTrainingDesktopChrome } from '@/utils/trainingClient'

const route = useRoute()
const authStore = useAuthStore()
const training = useTrainingStore()

const visible = computed(() => {
  if (shouldHideTrainingDesktopChrome(route.path)) return false
  if (!training.isActive || !training.snapshot.course_id) return false
  const mine = Number(authStore.user?.id)
  return mine > 0 && Number(training.snapshot.instructor_id) === mine
})

const canPrev = computed(() => canSteerLiveSnapshot(training.snapshot, -1))
const canNext = computed(() => canSteerLiveSnapshot(training.snapshot, 1))

function onMode(next: TrainingSteerMode): void {
  if (next === trainingSteerMode(training.snapshot)) return
  requestTrainingFree(next === 'free')
}

const railOpen = computed(() =>
  isTrainingRailVisible(authStore.isPlatformLevel, training.isActive)
)
const { padStyle } = useTrainingPadAnchor(railOpen)
</script>

<template>
  <div
    v-if="visible"
    class="instructor-pad"
    :style="padStyle"
  >
    <TrainingPlayControls
      :can-prev="canPrev"
      :can-next="canNext"
      :busy="training.busy"
      :mode="trainingSteerMode(training.snapshot)"
      @prev="requestTrainingStep(-1)"
      @next="requestTrainingStep(1)"
      @stop="requestTrainingEnd"
      @mode="onMode"
    />
  </div>
</template>

<style scoped>
.instructor-pad {
  position: fixed;
  right: max(1rem, env(safe-area-inset-right, 0px));
  bottom: max(1rem, env(safe-area-inset-bottom, 0px));
  z-index: 4300;
  overflow: visible;
}
</style>
