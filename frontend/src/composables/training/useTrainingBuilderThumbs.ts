import { onUnmounted, watch } from 'vue'

import {
  isPersistedTrainingThumb,
  persistTrainingStageThumb,
} from '@/composables/training/persistTrainingThumb'
import {
  isTrainingMediaStep,
  shouldRecaptureThumb,
} from '@/composables/training/trainingBuilderHibernate'
import {
  captureTrainingStage,
  trainingStepPageKey,
} from '@/composables/training/trainingStageThumb'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'

const CAPTURE_DELAY_MS = 400

export function useTrainingBuilderThumbs(): {
  rememberIfNeeded: () => Promise<void>
  persistAllPending: () => Promise<void>
} {
  const builder = useTrainingBuilderStore()
  let timer = 0
  let generation = 0

  async function persistThumbAt(index: number, url: string, pageKey: string): Promise<void> {
    const step = builder.steps[index]
    if (!builder.courseId || !step || isTrainingMediaStep(step)) return
    if (isPersistedTrainingThumb(url)) {
      if (!step.thumb_url) step.thumb_url = url
      return
    }
    try {
      const uploaded = await persistTrainingStageThumb(builder.courseId, url, index)
      if (builder.steps[index] !== step) return
      step.thumb_id = uploaded.id
      step.thumb_url = uploaded.url
      builder.writeThumb(index, uploaded.url, pageKey)
    } catch {
      return
    }
  }

  async function rememberCurrentThumb(): Promise<void> {
    window.clearTimeout(timer)
    const index = builder.selected
    const pageKey = trainingStepPageKey(builder.current)
    const token = (generation += 1)
    const url = await captureTrainingStage()
    if (token !== generation || !url) return
    builder.writeThumb(index, url, pageKey)
    await persistThumbAt(index, url, pageKey)
  }

  async function rememberIfNeeded(): Promise<void> {
    if (
      shouldRecaptureThumb(
        builder.thumbs[builder.selected],
        builder.thumbKeys[builder.selected],
        builder.current,
        builder.awake
      )
    ) {
      await rememberCurrentThumb()
      return
    }
    const url = builder.thumbs[builder.selected]
    if (url) {
      await persistThumbAt(builder.selected, url, builder.thumbKeys[builder.selected] || '')
    }
  }

  async function persistAllPending(): Promise<void> {
    for (let index = 0; index < builder.steps.length; index += 1) {
      const url = builder.thumbs[index]
      if (!url) continue
      await persistThumbAt(
        index,
        url,
        builder.thumbKeys[index] || trainingStepPageKey(builder.steps[index])
      )
    }
  }

  function scheduleThumb(): void {
    if (!builder.awake) return
    window.clearTimeout(timer)
    const index = builder.selected
    const pageKey = trainingStepPageKey(builder.current)
    const token = (generation += 1)
    timer = window.setTimeout(() => {
      void captureTrainingStage().then((url) => {
        if (token !== generation || !url) return
        builder.writeThumb(index, url, pageKey)
        void persistThumbAt(index, url, pageKey)
      })
    }, CAPTURE_DELAY_MS)
  }

  watch(() => trainingStepPageKey(builder.current), scheduleThumb)

  onUnmounted(() => {
    window.clearTimeout(timer)
    generation += 1
  })

  return {
    rememberIfNeeded,
    persistAllPending,
  }
}
