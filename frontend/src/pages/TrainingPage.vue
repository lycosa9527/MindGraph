<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import TrainingCourseGrid from '@/components/training/TrainingCourseGrid.vue'
import TrainingLandingHeader from '@/components/training/TrainingLandingHeader.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useTrainingHeartbeat } from '@/composables/training/useTrainingHeartbeat'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'
import type { TrainingCourse, TrainingOrgRow, TrainingReady } from '@/types/training'
import {
  TrainingApiError,
  endTraining,
  fetchActiveTraining,
  fetchTrainingCourses,
  fetchTrainingOrgs,
  fetchTrainingReady,
  pauseTraining,
  playTrainingCourse,
  resumeTraining,
  startTrainingSession,
  stepTrainingCourse,
  takeoverTraining,
} from '@/utils/trainingApi'

const STEER_GAP_MS = 550

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const training = useTrainingStore()

const orgs = ref<TrainingOrgRow[]>([])
const courses = ref<TrainingCourse[]>([])
const selectedOrgId = ref<number | null>(null)
const ready = ref<TrainingReady | null>(null)
const busy = ref(false)

const myUserId = computed(() => Number(authStore.user?.id))
const isForeignSession = computed(
  () =>
    training.isActive &&
    training.snapshot.instructor_id != null &&
    training.snapshot.instructor_id !== myUserId.value
)
const canControl = computed(() => training.isActive && !isForeignSession.value)
const canStart = computed(() =>
  Boolean(ready.value && selectedOrgId.value != null && !training.isActive)
)

useTrainingHeartbeat(() => Boolean(canControl.value && authStore.isPlatformLevel))

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

async function loadOrgs(query = ''): Promise<void> {
  const result = await fetchTrainingOrgs(query)
  orgs.value = result.items
}

async function selectOrg(orgId: number | null): Promise<void> {
  selectedOrgId.value = orgId
  training.leadingOrgId = orgId
  if (orgId == null) {
    ready.value = null
    return
  }
  ready.value = await fetchTrainingReady(orgId)
  training.applySnapshot(await fetchActiveTraining(orgId))
}

async function start(): Promise<boolean> {
  if (selectedOrgId.value == null || ready.value == null) {
    notify.warning(t('training.pickOrgFirst'))
    return false
  }
  busy.value = true
  try {
    const snap = await startTrainingSession(selectedOrgId.value, ready.value.teacher_total)
    training.applySnapshot(snap)
    return true
  } catch (error) {
    if (error instanceof TrainingApiError && error.code === 'instructor_busy') {
      notify.warning(t('training.hostedElsewhere'))
    } else if (error instanceof TrainingApiError && error.code === 'confirm_mismatch') {
      notify.warning(t('training.confirmMismatch'))
      ready.value = await fetchTrainingReady(selectedOrgId.value)
    } else if (error instanceof TrainingApiError && error.code === 'org_busy') {
      training.applySnapshot(await fetchActiveTraining(selectedOrgId.value))
      notify.warning(t('training.takeoverHint'))
    } else {
      notify.error(t('training.startFailed'))
    }
    return false
  } finally {
    busy.value = false
  }
}

async function applyCourse(course: TrainingCourse): Promise<void> {
  if (selectedOrgId.value == null) {
    notify.warning(t('training.pickOrgFirst'))
    return
  }
  if (isForeignSession.value) {
    notify.warning(t('training.takeoverHint'))
    return
  }
  if (!training.isActive) {
    const started = await start()
    if (!started) return
  }
  const snap = training.snapshot
  if (!snap.session_id || snap.org_id == null) return
  try {
    training.applySnapshot(await playTrainingCourse(snap.session_id, snap.org_id, course.id))
    await sleep(STEER_GAP_MS)
  } catch {
    notify.error(t('training.steerFailed'))
  }
}

async function pause(): Promise<void> {
  const snap = training.snapshot
  if (!snap.session_id || snap.org_id == null) return
  training.applySnapshot(await pauseTraining(snap.session_id, snap.org_id))
}

async function resume(): Promise<void> {
  const snap = training.snapshot
  if (!snap.session_id || snap.org_id == null) return
  training.applySnapshot(await resumeTraining(snap.session_id, snap.org_id))
}

async function end(): Promise<void> {
  const snap = training.snapshot
  if (!snap.session_id || snap.org_id == null) return
  training.applySnapshot(await endTraining(snap.session_id, snap.org_id))
}

async function takeover(): Promise<void> {
  const snap = training.snapshot
  if (!snap.session_id || snap.org_id == null) return
  training.applySnapshot(await takeoverTraining(snap.session_id, snap.org_id))
}

async function moveStep(delta: number): Promise<void> {
  const snap = training.snapshot
  if (!snap.session_id || snap.org_id == null) return
  try {
    training.applySnapshot(await stepTrainingCourse(snap.session_id, snap.org_id, { delta }))
  } catch {
    notify.error(t('training.steerFailed'))
  }
}

onMounted(() => {
  void loadOrgs()
  void fetchTrainingCourses().then((rows) => {
    courses.value = rows
  })
})
</script>

<template>
  <div class="training-page">
    <TrainingLandingHeader
      :orgs="orgs"
      :selected-org-id="selectedOrgId"
      :ready="ready"
      :busy="busy"
      :can-control="canControl"
      :is-live="training.isLive"
      :is-paused="training.isPaused"
      :is-foreign="isForeignSession"
      :has-course="Boolean(training.snapshot.course_id)"
      @search="loadOrgs"
      @select-org="selectOrg"
      @start="start"
      @pause="pause"
      @resume="resume"
      @end="end"
      @takeover="takeover"
      @prev-step="moveStep(-1)"
      @next-step="moveStep(1)"
    />
    <div class="training-page__body">
      <p
        v-if="canStart"
        class="training-page__hint"
      >
        {{ t('training.confirmStart') }}
      </p>
      <TrainingCourseGrid
        :courses="courses"
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
