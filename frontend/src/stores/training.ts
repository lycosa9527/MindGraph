import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import type { TrainingSnapshot, TrainingTopicOption } from '@/types/training'

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

export const useTrainingStore = defineStore('training', () => {
  const snapshot = ref<TrainingSnapshot>(emptySnapshot())
  const lastAppliedSeq = ref(0)
  const commandEtag = ref<string | null>(null)
  const pendingChip = ref<TrainingTopicOption | null>(null)
  const pendingJump = ref<TrainingTopicOption | null>(null)
  const leadingOrgId = ref<number | null>(null)
  const activityTick = ref(0)
  const uiFocusKey = ref<string | null>(null)

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

  function setPendingChip(option: TrainingTopicOption | null): void {
    pendingChip.value = option
  }

  function setPendingJump(option: TrainingTopicOption | null): void {
    pendingJump.value = option
  }

  function bumpActivity(): void {
    activityTick.value += 1
  }

  function setUiFocus(key: string | null): void {
    uiFocusKey.value = key
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
    bumpActivity,
    setUiFocus,
    isLive,
    isPaused,
    isActive,
    isFree,
    applySnapshot,
    markApplied,
    setPendingChip,
    setPendingJump,
    reset,
  }
})
