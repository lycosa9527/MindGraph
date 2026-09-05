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
  trainingStepThumbKey,
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

  async function persistThumbAt(
    index: number,
    url: string,
    pageKey: string,
    ignoreError = true
  ): Promise<void> {
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
    } catch (error) {
      if (ignoreError) return
      throw error
    }
  }

  async function rememberCurrentThumb(): Promise<void> {
    window.clearTimeout(timer)
    const index = builder.selected
    const captureKey = trainingStepThumbKey(builder.current)
    const token = (generation += 1)
    const url = await captureTrainingStage()
    if (token !== generation || !url) return
    builder.writeThumb(index, url, captureKey)
    await persistThumbAt(index, url, captureKey)
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
      await persistThumbAt(
        builder.selected,
        url,
        builder.thumbKeys[builder.selected] || trainingStepThumbKey(builder.current)
      )
    }
  }

  async function persistAllPending(): Promise<void> {
    for (let index = 0; index < builder.steps.length; index += 1) {
      const url = builder.thumbs[index]
      if (!url) continue
      await persistThumbAt(
        index,
        url,
        builder.thumbKeys[index] || trainingStepThumbKey(builder.steps[index]),
        false
      )
    }
  }

  function scheduleThumb(): void {
    if (!builder.awake) return
    window.clearTimeout(timer)
    const index = builder.selected
    const captureKey = trainingStepThumbKey(builder.current)
    const token = (generation += 1)
    timer = window.setTimeout(() => {
      void captureTrainingStage().then((url) => {
        if (token !== generation || !url) return
        builder.writeThumb(index, url, captureKey)
        void persistThumbAt(index, url, captureKey)
      })
    }, CAPTURE_DELAY_MS)
  }

  watch(() => trainingStepThumbKey(builder.current), scheduleThumb)

  onUnmounted(() => {
    window.clearTimeout(timer)
    generation += 1
  })

  return {
    rememberIfNeeded,
    persistAllPending,
  }
}
