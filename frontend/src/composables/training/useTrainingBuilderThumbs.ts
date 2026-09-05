import { onUnmounted, ref, watch, type Ref } from 'vue'

import {
  isTrainingMediaStep,
  shouldAwakeOnSelect,
  shouldRecaptureThumb,
} from '@/composables/training/trainingBuilderHibernate'
import {
  isPersistedTrainingThumb,
  persistTrainingStageThumb,
} from '@/composables/training/persistTrainingThumb'
import {
  captureTrainingStage,
  trainingStepPageKey,
} from '@/composables/training/trainingStageThumb'
import type { TrainingCourseStep } from '@/types/training'

const CAPTURE_DELAY_MS = 400

export function useTrainingBuilderThumbs(
  selected: Ref<number>,
  current: Ref<TrainingCourseStep | null>,
  steps: Ref<TrainingCourseStep[]>,
  courseId: Ref<string>
): {
  thumbs: Ref<(string | null)[]>
  thumbKeys: Ref<string[]>
  awake: Ref<boolean>
  rememberIfNeeded: () => Promise<void>
  persistAllPending: () => Promise<void>
  hydrateFromSteps: (rows: TrainingCourseStep[]) => void
  removeThumb: (index: number) => void
  insertThumbs: (index: number, urls: (string | null)[]) => void
  wake: () => void
  applySelectAwake: (index: number, step: TrainingCourseStep | null | undefined) => void
} {
  const thumbs = ref<(string | null)[]>([])
  const thumbKeys = ref<string[]>([])
  const awake = ref(true)
  let timer = 0
  let generation = 0

  function writeThumb(index: number, url: string | null, pageKey: string): void {
    if (index < 0 || !url) return
    const next = thumbs.value.slice()
    const keys = thumbKeys.value.slice()
    while (next.length <= index) next.push(null)
    while (keys.length <= index) keys.push('')
    next[index] = url
    keys[index] = pageKey
    thumbs.value = next
    thumbKeys.value = keys
  }

  async function persistThumbAt(index: number, url: string, pageKey: string): Promise<void> {
    const step = steps.value[index]
    if (!courseId.value || !step || isTrainingMediaStep(step)) return
    if (isPersistedTrainingThumb(url)) {
      if (!step.thumb_url) step.thumb_url = url
      return
    }
    try {
      const uploaded = await persistTrainingStageThumb(courseId.value, url, index)
      if (steps.value[index] !== step) return
      step.thumb_id = uploaded.id
      step.thumb_url = uploaded.url
      writeThumb(index, uploaded.url, pageKey)
    } catch {
      return
    }
  }

  async function rememberCurrentThumb(): Promise<void> {
    window.clearTimeout(timer)
    const index = selected.value
    const pageKey = trainingStepPageKey(current.value)
    const token = (generation += 1)
    const url = await captureTrainingStage()
    if (token !== generation || !url) return
    writeThumb(index, url, pageKey)
    await persistThumbAt(index, url, pageKey)
  }

  async function rememberIfNeeded(): Promise<void> {
    if (
      shouldRecaptureThumb(
        thumbs.value[selected.value],
        thumbKeys.value[selected.value],
        current.value,
        awake.value
      )
    ) {
      await rememberCurrentThumb()
      return
    }
    const url = thumbs.value[selected.value]
    if (url) {
      await persistThumbAt(selected.value, url, thumbKeys.value[selected.value] || '')
    }
  }

  async function persistAllPending(): Promise<void> {
    for (let index = 0; index < steps.value.length; index += 1) {
      const url = thumbs.value[index]
      if (!url) continue
      await persistThumbAt(index, url, thumbKeys.value[index] || trainingStepPageKey(steps.value[index]))
    }
  }

  function scheduleThumb(): void {
    if (!awake.value) return
    window.clearTimeout(timer)
    const index = selected.value
    const pageKey = trainingStepPageKey(current.value)
    const token = (generation += 1)
    timer = window.setTimeout(() => {
      void captureTrainingStage().then((url) => {
        if (token !== generation || !url) return
        writeThumb(index, url, pageKey)
        void persistThumbAt(index, url, pageKey)
      })
    }, CAPTURE_DELAY_MS)
  }

  function hydrateFromSteps(rows: TrainingCourseStep[]): void {
    window.clearTimeout(timer)
    generation += 1
    thumbs.value = rows.map((step) => {
      if (step.thumb_url) return step.thumb_url
      return isTrainingMediaStep(step) ? step.asset_url || null : null
    })
    thumbKeys.value = rows.map((step, index) =>
      thumbs.value[index] ? trainingStepPageKey(step) : ''
    )
    awake.value = shouldAwakeOnSelect(thumbs.value[selected.value], rows[selected.value] || null)
  }

  function removeThumb(index: number): void {
    const next = thumbs.value.slice()
    const keys = thumbKeys.value.slice()
    next.splice(index, 1)
    keys.splice(index, 1)
    thumbs.value = next
    thumbKeys.value = keys
  }

  function insertThumbs(index: number, urls: (string | null)[]): void {
    if (!urls.length) return
    const next = thumbs.value.slice()
    const keys = thumbKeys.value.slice()
    const at = Math.max(0, index)
    while (next.length < at) next.push(null)
    while (keys.length < at) keys.push('')
    next.splice(at, 0, ...urls)
    keys.splice(at, 0, ...urls.map(() => ''))
    thumbs.value = next
    thumbKeys.value = keys
  }

  function wake(): void {
    awake.value = true
  }

  function applySelectAwake(
    index: number,
    step: TrainingCourseStep | null | undefined
  ): void {
    awake.value = shouldAwakeOnSelect(thumbs.value[index], step)
  }

  watch(() => trainingStepPageKey(current.value), scheduleThumb)

  onUnmounted(() => {
    window.clearTimeout(timer)
    generation += 1
  })

  return {
    thumbs,
    thumbKeys,
    awake,
    rememberIfNeeded,
    persistAllPending,
    hydrateFromSteps,
    removeThumb,
    insertThumbs,
    wake,
    applySelectAwake,
  }
}
