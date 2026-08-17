/**
 * Ask Kitty to synthesize lecture captions into the lookahead buffer.
 */
import { eventBus } from '@/composables/core/useEventBus'
import type { MindClassroomRemoteStep } from '@/composables/mindMap/mindClassroomJobApi'
import { useMindClassroomStore } from '@/stores/mindClassroom'
import { mapRemoteLectureSteps } from '@/utils/mindClassroomRemoteSteps'
import type { MindClassroomLectureStep } from '@/utils/mindClassroomScript'

const CATCHUP_SLIDES = 3

const requestedPrefetchIds = new Set<string>()

export function resetLectureTtsCatchup(): void {
  requestedPrefetchIds.clear()
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

export function requestLectureCatchupPrefetch(
  steps: readonly MindClassroomLectureStep[],
  voiceEnabled: boolean
): void {
  if (!voiceEnabled) return
  let sent = 0
  for (const step of steps) {
    if (sent >= CATCHUP_SLIDES) return
    if (!step.caption.trim()) continue
    requestLectureSlidePrefetch(step)
    sent += 1
  }
}

export function beginFirstLectureSlideWarmup(
  steps: readonly MindClassroomLectureStep[],
  voiceEnabled: boolean
): void {
  const store = useMindClassroomStore()
  const first = steps[0]
  if (first && store.preparedSteps[0]?.id && store.preparedSteps[0].id !== first.id) {
    resetLectureTtsCatchup()
  }
  if (
    first &&
    store.preparedSteps[0]?.id === first.id &&
    (store.voiceWarmup === 'loading' || store.voiceWarmup === 'ready')
  ) {
    requestLectureCatchupPrefetch(steps, voiceEnabled)
    return
  }
  if (!voiceEnabled || !first?.caption.trim()) {
    store.setVoiceWarmup('ready')
    return
  }
  store.setVoiceWarmup('loading')
  requestLectureCatchupPrefetch(steps, voiceEnabled)
}

export function markLectureVoiceWarmupReady(stepId?: string): void {
  const store = useMindClassroomStore()
  const first = store.preparedSteps[0]
  if (stepId && first?.id && stepId !== first.id) return
  if (store.voiceWarmup !== 'loading') return
  store.setVoiceWarmup('ready')
}

export function tryWarmupFromJobSteps(
  rawSteps: MindClassroomRemoteStep[] | null | undefined,
  liveIds: Set<string>,
  voiceEnabled: boolean
): boolean {
  const store = useMindClassroomStore()
  const mapped = mapRemoteLectureSteps(rawSteps ?? [], liveIds)
  if (!mapped[0]?.caption.trim()) return false
  const grew = mapped.length > store.preparedSteps.length
  if (grew || store.preparedSteps.length === 0) {
    store.setPreparedSteps(mapped)
  }
  if (store.voiceWarmup === 'idle') {
    resetLectureTtsCatchup()
    beginFirstLectureSlideWarmup(mapped, voiceEnabled)
    return true
  }
  if (grew) {
    requestLectureCatchupPrefetch(mapped, voiceEnabled)
  }
  return grew
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
      markLectureVoiceWarmupReady(payload.stepId)
    },
    owner
  )
}
