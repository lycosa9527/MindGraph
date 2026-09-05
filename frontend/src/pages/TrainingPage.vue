<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import TrainingCourseGrid from '@/components/training/TrainingCourseGrid.vue'
import TrainingLandingHeader from '@/components/training/TrainingLandingHeader.vue'
import TrainingLandingPreview from '@/components/training/TrainingLandingPreview.vue'
import { useLanguage, useNotifications } from '@/composables'
import { isTrainingRoomArmed } from '@/composables/training/applyTrainingSnapshot'
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
import { fetchTrainingCourse } from '@/utils/trainingApi'

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const training = useTrainingStore()
const preview = ref<TrainingCourse | null>(null)
const previewIndex = ref(0)

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
const roomArmed = computed(() => canControl.value && isTrainingRoomArmed(training.snapshot))

useTrainingHeartbeat(() => Boolean(canControl.value && authStore.isPlatformLevel))

async function applyCourse(course: TrainingCourse): Promise<void> {
  if (training.selectedOrgId == null) {
    try {
      const full = await fetchTrainingCourse(course.id)
      if (!full.steps?.length) {
        notify.warning(t('training.builder.previewEmpty'))
        return
      }
      preview.value = full
      previewIndex.value = 0
    } catch {
      notify.error(t('training.builder.previewEmpty'))
    }
    return
  }
  requestTrainingPlay(course.id)
}

function onSelectOrg(orgId: number | null): void {
  preview.value = null
  requestTrainingSelectOrg(orgId)
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
      @select-org="onSelectOrg"
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
      <p
        v-else-if="roomArmed"
        class="training-page__hint"
      >
        {{ t('training.moduleReady') }}
      </p>
      <p
        v-else-if="training.selectedOrgId == null"
        class="training-page__hint"
      >
        {{ t('training.builder.previewHint') }}
      </p>
      <TrainingCourseGrid
        :courses="training.courses"
        :active-course-id="training.snapshot.course_id ?? null"
        @select="applyCourse"
      />
    </div>
    <TrainingLandingPreview
      v-if="preview"
      :course="preview"
      :index="previewIndex"
      @close="preview = null"
      @index="previewIndex = $event"
    />
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
