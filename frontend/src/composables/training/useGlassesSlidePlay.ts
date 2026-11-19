/**
 * The open course is what the bound glasses show.
 * A tap on the glasses asks this computer to advance, then the glasses follow.
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { playGlassesReveal } from '@/composables/training/glassesSlideReveal'
import { flushPublishedBuilderSpec } from '@/composables/training/trainingCanvasSpec'
import { requestTrainingStep } from '@/composables/training/trainingCommands'
import { interactReadCursor } from '@/composables/training/trainingInteract'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import { apiRequest } from '@/utils/apiClient'
import { shouldSkipTrainingFollow } from '@/utils/trainingClient'

type ShownSlide = {
  courseId: string
  index: number
  mark: number
  read: number
  orgId: number
}

/** While the glasses are speaking a slide, the computer stays quiet. */
export const glassesHoldVoice = ref(false)

export function useGlassesCourseSync(): void {
  const builder = useTrainingBuilderStore()
  const training = useTrainingStore()
  const auth = useAuthStore()
  let source: EventSource | null = null
  let pulling = false
  let pullAgain = false
  let lastSent = ''
  let lastOrgId = 0

  const mine = computed(() => Number(auth.user?.id) || 0)

  const hosted = computed<ShownSlide | null>(() => {
    const snap = training.snapshot
    if (snap.state !== 'live' && snap.state !== 'paused') return null
    const courseId = (snap.course_id || '').trim()
    const step = snap.step
    const teaching = mine.value > 0 && Number(snap.instructor_id) === mine.value
    if (!courseId || !step || !teaching) return null
    return {
      courseId,
      index: snap.step_index ?? 0,
      mark: step.mark_step ?? 1,
      read: step.interact?.play_index ?? 0,
      orgId: snap.org_id ?? 0,
    }
  })

  const audience = computed(() => {
    const snap = training.snapshot
    const active = snap.state === 'live' || snap.state === 'paused'
    const courseId = (snap.course_id || '').trim()
    const someoneElse = mine.value > 0 && Number(snap.instructor_id) !== mine.value
    return active && Boolean(courseId) && someoneElse
  })

  const preview = computed<ShownSlide | null>(() => {
    if (hosted.value || audience.value || !builder.previewing) return null
    const courseId = builder.courseId.trim()
    const step = builder.current
    if (!courseId || !step) return null
    return {
      courseId,
      index: builder.selected,
      mark: step.mark_step ?? 1,
      read: step.interact?.play_index ?? interactReadCursor.value,
      orgId: 0,
    }
  })

  const shown = computed(() => (audience.value ? null : (hosted.value ?? preview.value)))

  function signature(slide: ShownSlide, done = false): string {
    return `${slide.courseId}:${slide.index}:${slide.mark}:${slide.read}:${done ? 1 : 0}`
  }

  async function publish(slide: ShownSlide | null, done = false): Promise<void> {
    const key = slide ? signature(slide, done) : `idle:${lastOrgId}`
    if (key === lastSent) return
    lastSent = key
    glassesHoldVoice.value = Boolean(slide && !done)
    const orgId = slide?.orgId || lastOrgId
    if (slide?.orgId) lastOrgId = slide.orgId
    if (!slide) lastOrgId = 0
    try {
      const response = await apiRequest('/api/learning-space/glasses/follow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_id: slide?.courseId ?? '',
          index: slide?.index ?? -1,
          mark: slide?.mark ?? 1,
          read: slide?.read ?? 0,
          done,
          org_id: orgId,
        }),
      })
      if (!response.ok) lastSent = ''
    } catch {
      lastSent = ''
    }
  }

  function revealSlide(slide: ShownSlide, previous: ShownSlide | null): void {
    if (hosted.value) return
    if (previous && previous.courseId === slide.courseId && previous.index === slide.index) return
    const step = builder.steps[slide.index]
    const reveal = step?.glasses_reveal || ''
    const root = document.querySelector('.builder-stage') ?? document.querySelector('.vue-flow')
    if (!(root instanceof HTMLElement)) return
    const pace = step?.glasses_pace
    void playGlassesReveal(root, reveal, typeof pace === 'number' ? pace : 280)
  }

  function advancePreview(slide: ShownSlide): void {
    const before = signature(slide)
    const next = builder.previewIndex(1)
    if (next !== builder.selected) {
      flushPublishedBuilderSpec()
      builder.applySelectAwake(next, builder.steps[next])
      builder.setSelected(next)
    }
    const after = preview.value
    if (!after || signature(after) === before) void publish(slide, true)
  }

  async function onNext(courseId: string): Promise<void> {
    const current = shown.value
    if (!current || current.courseId !== courseId) return
    if (hosted.value) {
      requestTrainingStep(1)
      return
    }
    advancePreview(current)
  }

  async function pull(): Promise<void> {
    if (pulling) {
      pullAgain = true
      return
    }
    pulling = true
    try {
      do {
        pullAgain = false
        const response = await apiRequest('/api/learning-space/glasses/play')
        if (response.status === 401 || response.status === 403) {
          closeSource()
          return
        }
        if (!response.ok) return
        const body = (await response.json()) as { play?: { action?: string; course_id?: string } }
        const cue = body.play
        if (!cue || cue.action !== 'next' || !cue.course_id) continue
        await onNext(cue.course_id)
      } while (pullAgain)
    } catch {
      // A missed cue stays queued until the next event.
    } finally {
      pulling = false
    }
  }

  function closeSource(): void {
    source?.close()
    source = null
  }

  function openSource(): void {
    if (source || shouldSkipTrainingFollow() || typeof EventSource === 'undefined') return
    if (!auth.isAuthenticated) return
    const next = new EventSource('/api/learning-space/glasses/events', { withCredentials: true })
    next.addEventListener('play', () => {
      void pull()
    })
    next.addEventListener('remote', () => {
      eventBus.emit('glasses:nudge', {})
    })
    next.onopen = () => {
      void pull()
      eventBus.emit('glasses:nudge', {})
    }
    next.onerror = () => {
      if (!auth.isAuthenticated) closeSource()
    }
    source = next
  }

  watch(shown, (next, previous) => {
    if (audience.value) return
    void publish(next)
    if (next) revealSlide(next, previous)
  })

  watch(
    () => auth.isAuthenticated,
    (ready) => {
      if (ready) openSource()
      else closeSource()
    },
    { immediate: true }
  )

  onUnmounted(() => {
    closeSource()
    glassesHoldVoice.value = false
  })
}
