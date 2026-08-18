/**
 * Ask Kitty to synthesize lecture captions into the lookahead buffer.
 */
import { watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import type { MindClassroomRemoteStep } from '@/composables/mindMap/mindClassroomJobApi'
import { useMindClassroomStore } from '@/stores/mindClassroom'
import {
  collectLiveNodeIds,
  mapRemoteLectureSteps,
  type LectureLiveRef,
} from '@/utils/mindClassroomRemoteSteps'
import type { MindClassroomLectureStep } from '@/utils/mindClassroomScript'

const requestedPrefetchIds = new Set<string>()
let warmupPrepKey = ''

export function resetLectureTtsCatchup(): void {
  requestedPrefetchIds.clear()
  warmupPrepKey = ''
}

export function requestLectureSlidePrefetch(step: MindClassroomLectureStep | undefined): void {
  const text = step?.caption.trim()
  if (!text || !step) return
  if (requestedPrefetchIds.has(step.id)) return
  requestedPrefetchIds.add(step.id)
  eventBus.emit('kitty:lecture_prefetch_requested', {
    text,
    stepId: step.id,
  })
}

export function requestFirstLectureSlidePrefetch(
  steps: readonly MindClassroomLectureStep[]
): void {
  requestLectureSlidePrefetch(steps[0])
}

export function beginFirstLectureSlideWarmup(
  steps: readonly MindClassroomLectureStep[],
  voiceEnabled: boolean
): void {
  const store = useMindClassroomStore()
  if (!store.isLaunchActive) return
  warmupPrepKey = store.activePrepKey
  const first = steps[0]
  const sameOpening = Boolean(first?.id) && store.preparedSteps[0]?.id === first.id
  const alreadyRequested = Boolean(first?.id) && requestedPrefetchIds.has(first.id)
  if (
    sameOpening &&
    alreadyRequested &&
    (store.voiceWarmup === 'loading' || store.voiceWarmup === 'ready')
  ) {
    return
  }
  resetLectureTtsCatchup()
  warmupPrepKey = store.activePrepKey
  if (!voiceEnabled || !first?.caption.trim()) {
    const alreadyReady = store.voiceWarmup === 'ready'
    store.setVoiceWarmup('ready')
    if (!alreadyReady) emitClassroomReady()
    return
  }
  store.setVoiceWarmup('loading')
  requestFirstLectureSlidePrefetch(steps)
}

export function emitClassroomReady(): void {
  const store = useMindClassroomStore()
  if (store.isLecturing || !store.preparedSteps.length) return
  eventBus.emit('classroom:ready', {})
}

function warmupBelongsToActiveSlot(): boolean {
  const store = useMindClassroomStore()
  return !warmupPrepKey || warmupPrepKey === store.activePrepKey
}

export function markLectureVoiceWarmupReady(stepId?: string): void {
  const store = useMindClassroomStore()
  if (!warmupBelongsToActiveSlot()) return
  const first = store.preparedSteps[0]
  if (stepId && first?.id && stepId !== first.id) return
  if (store.voiceWarmup !== 'loading') return
  store.setVoiceWarmup('ready')
  emitClassroomReady()
}

export function markLectureVoiceWarmupFailed(stepId?: string): void {
  const store = useMindClassroomStore()
  if (!warmupBelongsToActiveSlot()) return
  const first = store.preparedSteps[0]
  if (stepId && first?.id && stepId !== first.id) return
  if (store.voiceWarmup !== 'loading') return
  store.setVoiceWarmup('failed')
}

export function tryWarmupFromJobSteps(
  rawSteps: MindClassroomRemoteStep[] | null | undefined,
  live: LectureLiveRef,
  voiceEnabled: boolean
): boolean {
  const store = useMindClassroomStore()
  const mapped = mapRemoteLectureSteps(rawSteps ?? [], live)
  if (!mapped[0]?.caption.trim()) return false
  const grew = mapped.length > store.preparedSteps.length
  if (grew || store.preparedSteps.length === 0) {
    const snapshotIds =
      live instanceof Set ? [...live] : [...collectLiveNodeIds(live)]
    store.setPreparedSteps(mapped, snapshotIds)
  }
  if (store.voiceWarmup === 'idle' && store.isLaunchActive) {
    resetLectureTtsCatchup()
    beginFirstLectureSlideWarmup(mapped, voiceEnabled)
    return true
  }
  return grew
}

export function bindClassroomLaunchToModal(): void {
  const store = useMindClassroomStore()
  watch(
    () => store.modalOpen,
    (open) => {
      if (!open || store.isLecturing) return
      eventBus.emit('classroom:restore_prepared_requested', {})
      if (!store.preparedSteps.length) return
      beginFirstLectureSlideWarmup(store.preparedSteps, store.voiceEnabled)
    },
    { immediate: true }
  )
}

export function bindLectureVoiceWarmupEvents(owner: string): void {
  eventBus.onWithOwner(
    'kitty:lecture_prefetch_ready',
    (payload) => {
      markLectureVoiceWarmupReady(payload.stepId)
    },
    owner
  )
  eventBus.onWithOwner(
    'kitty:lecture_prefetch_failed',
    (payload) => {
      markLectureVoiceWarmupFailed(payload.stepId)
    },
    owner
  )
}
