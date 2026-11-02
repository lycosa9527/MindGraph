import { onUnmounted, watch } from 'vue'

import {
  builderDiagramNodes,
  isBoundToStep,
} from '@/composables/training/builderDiagramBridge'
import {
  isPersistedTrainingThumb,
  persistTrainingStageThumb,
} from '@/composables/training/persistTrainingThumb'
import {
  canCommitBuilderThumb,
  isTrainingMediaStep,
  shouldRecaptureThumb,
} from '@/composables/training/trainingBuilderHibernate'
import { flushPublishedBuilderSpec } from '@/composables/training/trainingCanvasSpec'
import {
  captureTrainingStage,
  trainingStepThumbKey,
} from '@/composables/training/trainingStageThumb'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import type { TrainingCourseStep } from '@/types/training'

const CAPTURE_DELAY_MS = 400

export function useTrainingBuilderThumbs(): {
  rememberIfNeeded: () => Promise<void>
  persistAllPending: () => Promise<void>
} {
  const builder = useTrainingBuilderStore()
  let timer = 0
  let generation = 0

  function liveNodeFingerprint(): string {
    return builderDiagramNodes.value.map((node) => `${node.id}:${node.text}`).join('|')
  }

  function acceptLiveCapture(index: number, step: TrainingCourseStep | null): boolean {
    return canCommitBuilderThumb(
      builder.selected,
      index,
      step,
      Boolean(step && builder.steps[index] === step && isBoundToStep(step))
    )
  }

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
    const step = builder.current
    const captureKey = trainingStepThumbKey(step)
    const token = (generation += 1)
    const url = await captureTrainingStage()
    if (token !== generation || !url || !acceptLiveCapture(index, step)) return
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
    flushPublishedBuilderSpec()
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
    const step = builder.current
    const captureKey = trainingStepThumbKey(step)
    const token = (generation += 1)
    timer = window.setTimeout(() => {
      void captureTrainingStage().then((url) => {
        if (token !== generation || !url || !acceptLiveCapture(index, step)) return
        builder.writeThumb(index, url, captureKey)
        void persistThumbAt(index, url, captureKey)
      })
    }, CAPTURE_DELAY_MS)
  }

  watch(
    () => [builder.selected, trainingStepThumbKey(builder.current), liveNodeFingerprint()] as const,
    scheduleThumb
  )

  onUnmounted(() => {
    window.clearTimeout(timer)
    generation += 1
  })

  return {
    rememberIfNeeded,
    persistAllPending,
  }
}
