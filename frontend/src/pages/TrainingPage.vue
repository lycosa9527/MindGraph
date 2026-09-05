<script setup lang="ts">
import { computed, onMounted } from 'vue'

import TrainingCourseGrid from '@/components/training/TrainingCourseGrid.vue'
import TrainingLandingHeader from '@/components/training/TrainingLandingHeader.vue'
import { useLanguage } from '@/composables'
import {
  requestTrainingEnd,
  requestTrainingPause,
  requestTrainingPlay,
  requestTrainingResume,
  requestTrainingSearchOrgs,
  requestTrainingSelectOrg,
  requestTrainingStart,
  requestTrainingStep,
  requestTrainingTakeover,
} from '@/composables/training/trainingCommands'
import { useTrainingHeartbeat } from '@/composables/training/useTrainingHeartbeat'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'
import type { TrainingCourse } from '@/types/training'

const { t } = useLanguage()
const authStore = useAuthStore()
const training = useTrainingStore()

const myUserId = computed(() => Number(authStore.user?.id))
const isForeignSession = computed(
  () =>
    training.isActive &&
    training.snapshot.instructor_id != null &&
    training.snapshot.instructor_id !== myUserId.value
)
const canControl = computed(() => training.isActive && !isForeignSession.value)
const canStart = computed(() =>
  Boolean(training.ready && training.selectedOrgId != null && !training.isActive)
)

useTrainingHeartbeat(() => Boolean(canControl.value && authStore.isPlatformLevel))

function applyCourse(course: TrainingCourse): void {
  requestTrainingPlay(course.id)
}

onMounted(() => {
  void training.loadOrgs()
  void training.loadCourses()
})
</script>

<template>
  <div class="training-page">
    <TrainingLandingHeader
      :orgs="training.orgs"
      :selected-org-id="training.selectedOrgId"
      :ready="training.ready"
      :busy="training.busy"
      :can-control="canControl"
      :is-live="training.isLive"
      :is-paused="training.isPaused"
      :is-foreign="isForeignSession"
      :has-course="Boolean(training.snapshot.course_id)"
      @search="requestTrainingSearchOrgs"
      @select-org="requestTrainingSelectOrg"
      @start="requestTrainingStart"
      @pause="requestTrainingPause"
      @resume="requestTrainingResume"
      @end="requestTrainingEnd"
      @takeover="requestTrainingTakeover"
      @prev-step="requestTrainingStep(-1)"
      @next-step="requestTrainingStep(1)"
    />
    <div class="training-page__body">
      <p
        v-if="canStart"
        class="training-page__hint"
      >
        {{ t('training.confirmStart') }}
      </p>
      <TrainingCourseGrid
        :courses="training.courses"
        :active-course-id="training.snapshot.course_id ?? null"
        @select="applyCourse"
      />
    </div>
  </div>
</template>

<style scoped>
.training-page {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  background: #fafaf9;
}
.training-page__body {
  flex: 1;
  overflow: auto;
  padding: 1.25rem 1.5rem 2rem;
}
.training-page__hint {
  max-width: 56rem;
  margin: 0 auto 1.25rem;
  color: #78716c;
  font-size: 0.85rem;
}
</style>
