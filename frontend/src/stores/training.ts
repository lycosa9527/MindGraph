import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import type {
  TrainingCourse,
  TrainingOrgRow,
  TrainingReady,
  TrainingRosterRow,
  TrainingRosterSummary,
  TrainingSnapshot,
  TrainingTopicOption,
} from '@/types/training'
import {
  TrainingApiError,
  endTraining,
  fetchActiveTraining,
  fetchTrainingCourses,
  fetchTrainingOrgs,
  fetchTrainingReady,
  fetchTrainingRoster,
  fetchTrainingRosterSummary,
  freeTraining,
  pauseTraining,
  playTrainingCourse,
  resumeTraining,
  startTrainingSession,
  stepTrainingCourse,
  takeoverTraining,
} from '@/utils/trainingApi'
import { TRAINING_RAIL_PAGE_SIZE } from '@/utils/trainingClient'

const STEER_GAP_MS = 550

const emptySnapshot = (): TrainingSnapshot => ({
  state: 'none',
  session_id: null,
  org_id: null,
  seq: 0,
  diagram_type: null,
  topic_options: [],
  instructor_id: null,
  instructor_name: null,
  course_id: null,
  step_index: 0,
  step_count: 0,
  step: null,
  pull_users: true,
})

const emptyRosterSummary = (): TrainingRosterSummary => ({
  online: 0,
  generating: 0,
  done: 0,
})

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

export type TrainingStartCode =
  | 'ok'
  | 'pick_org'
  | 'instructor_busy'
  | 'confirm_mismatch'
  | 'org_busy'
  | 'failed'

export const useTrainingStore = defineStore('training', () => {
  const snapshot = ref<TrainingSnapshot>(emptySnapshot())
  const lastAppliedSeq = ref(0)
  const commandEtag = ref<string | null>(null)
  const pendingChip = ref<TrainingTopicOption | null>(null)
  const pendingJump = ref<TrainingTopicOption | null>(null)
  const leadingOrgId = ref<number | null>(null)
  const activityTick = ref(0)
  const uiFocusKey = ref<string | null>(null)
  const topicsDragLive = ref(false)

  const orgs = ref<TrainingOrgRow[]>([])
  const courses = ref<TrainingCourse[]>([])
  const selectedOrgId = ref<number | null>(null)
  const ready = ref<TrainingReady | null>(null)
  const busy = ref(false)

  const rosterRows = ref<TrainingRosterRow[]>([])
  const rosterTotal = ref(0)
  const rosterSummary = ref<TrainingRosterSummary>(emptyRosterSummary())
  const rosterLoading = ref(false)

  const isLive = computed(() => snapshot.value.state === 'live')
  const isPaused = computed(() => snapshot.value.state === 'paused')
  const isActive = computed(() => isLive.value || isPaused.value)
  const isFree = computed(() => isLive.value && snapshot.value.pull_users === false)

  function applySnapshot(next: TrainingSnapshot): void {
    if (next.seq < snapshot.value.seq && next.state !== 'none') {
      return
    }
    snapshot.value = next
  }

  function markApplied(seq: number): void {
    if (seq > lastAppliedSeq.value) {
      lastAppliedSeq.value = seq
    }
  }

  function setCommandEtag(etag: string | null): void {
    commandEtag.value = etag
  }

  function setLeadingOrgId(orgId: number | null): void {
    leadingOrgId.value = orgId
  }

  function setPendingChip(option: TrainingTopicOption | null): void {
    pendingChip.value = option
  }

  function setPendingJump(option: TrainingTopicOption | null): void {
    pendingJump.value = option
  }

  function setTopicsDragLive(next: boolean): void {
    topicsDragLive.value = next
  }

  function bumpActivity(): void {
    activityTick.value += 1
  }

  function setUiFocus(key: string | null): void {
    uiFocusKey.value = key
  }

  function sessionIds(): { sessionId: string; orgId: number } | null {
    const sessionId = snapshot.value.session_id
    const orgId = snapshot.value.org_id
    if (!sessionId || orgId == null) return null
    return { sessionId, orgId }
  }

  async function loadOrgs(query = ''): Promise<void> {
    const result = await fetchTrainingOrgs(query)
    orgs.value = result.items
  }

  async function loadCourses(): Promise<void> {
    courses.value = await fetchTrainingCourses()
  }

  async function selectOrg(orgId: number | null): Promise<void> {
    selectedOrgId.value = orgId
    setLeadingOrgId(orgId)
    if (orgId == null) {
      ready.value = null
      return
    }
    ready.value = await fetchTrainingReady(orgId)
    applySnapshot(await fetchActiveTraining(orgId))
  }

  async function startSession(): Promise<TrainingStartCode> {
    if (selectedOrgId.value == null || ready.value == null) return 'pick_org'
    busy.value = true
    try {
      applySnapshot(await startTrainingSession(selectedOrgId.value, ready.value.teacher_total))
      return 'ok'
    } catch (error) {
      if (error instanceof TrainingApiError && error.code === 'instructor_busy') {
        return 'instructor_busy'
      }
      if (error instanceof TrainingApiError && error.code === 'confirm_mismatch') {
        ready.value = await fetchTrainingReady(selectedOrgId.value)
        return 'confirm_mismatch'
      }
      if (error instanceof TrainingApiError && error.code === 'org_busy') {
        applySnapshot(await fetchActiveTraining(selectedOrgId.value))
        return 'org_busy'
      }
      return 'failed'
    } finally {
      busy.value = false
    }
  }

  async function playCourse(courseId: string): Promise<void> {
    const ids = sessionIds()
    if (!ids) return
    applySnapshot(await playTrainingCourse(ids.sessionId, ids.orgId, courseId))
    await sleep(STEER_GAP_MS)
  }

  async function pauseSession(): Promise<void> {
    const ids = sessionIds()
    if (!ids) return
    applySnapshot(await pauseTraining(ids.sessionId, ids.orgId))
  }

  async function resumeSession(): Promise<void> {
    const ids = sessionIds()
    if (!ids) return
    applySnapshot(await resumeTraining(ids.sessionId, ids.orgId))
  }

  async function endSession(): Promise<void> {
    const ids = sessionIds()
    if (!ids) return
    applySnapshot(await endTraining(ids.sessionId, ids.orgId))
  }

  async function takeoverSession(): Promise<void> {
    const ids = sessionIds()
    if (!ids) return
    applySnapshot(await takeoverTraining(ids.sessionId, ids.orgId))
  }

  async function stepSession(delta: number): Promise<void> {
    const ids = sessionIds()
    if (!ids) return
    applySnapshot(await stepTrainingCourse(ids.sessionId, ids.orgId, { delta }))
  }

  async function freeSession(free = true): Promise<void> {
    const ids = sessionIds()
    if (!ids) return
    applySnapshot(await freeTraining(ids.sessionId, ids.orgId, free))
  }

  async function fetchRoster(append = false): Promise<void> {
    const ids = sessionIds()
    if (!ids || rosterLoading.value) return
    rosterLoading.value = true
    try {
      if (append) {
        const list = await fetchTrainingRoster(
          ids.sessionId,
          ids.orgId,
          rosterRows.value.length,
          TRAINING_RAIL_PAGE_SIZE
        )
        rosterRows.value = [...rosterRows.value, ...list.items]
        rosterTotal.value = list.total
        return
      }
      const [list, counts] = await Promise.all([
        fetchTrainingRoster(ids.sessionId, ids.orgId, 0),
        fetchTrainingRosterSummary(ids.sessionId, ids.orgId),
      ])
      rosterRows.value = list.items
      rosterTotal.value = list.total
      rosterSummary.value = counts
    } finally {
      rosterLoading.value = false
    }
  }

  function reset(): void {
    snapshot.value = emptySnapshot()
    lastAppliedSeq.value = 0
    commandEtag.value = null
    pendingChip.value = null
    pendingJump.value = null
    leadingOrgId.value = null
    activityTick.value = 0
    uiFocusKey.value = null
    topicsDragLive.value = false
    rosterRows.value = []
    rosterTotal.value = 0
    rosterSummary.value = emptyRosterSummary()
    rosterLoading.value = false
  }

  return {
    snapshot,
    lastAppliedSeq,
    commandEtag,
    pendingChip,
    pendingJump,
    leadingOrgId,
    activityTick,
    uiFocusKey,
    topicsDragLive,
    orgs,
    courses,
    selectedOrgId,
    ready,
    busy,
    rosterRows,
    rosterTotal,
    rosterSummary,
    rosterLoading,
    isLive,
    isPaused,
    isActive,
    isFree,
    applySnapshot,
    markApplied,
    setCommandEtag,
    setLeadingOrgId,
    setPendingChip,
    setPendingJump,
    setTopicsDragLive,
    bumpActivity,
    setUiFocus,
    loadOrgs,
    loadCourses,
    selectOrg,
    startSession,
    playCourse,
    pauseSession,
    resumeSession,
    endSession,
    takeoverSession,
    stepSession,
    freeSession,
    fetchRoster,
    reset,
  }
})
