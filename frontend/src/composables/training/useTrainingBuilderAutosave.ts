import { onUnmounted, ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import {
  mergeSavedStepMeta,
  trainingCourseFingerprint,
  trainingCourseWriteBody,
} from '@/composables/training/trainingBuilderSteps'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import { saveTrainingCourse } from '@/utils/trainingApi'

export type TrainingBuilderSyncState = 'idle' | 'saving' | 'saved' | 'error'

const AUTOSAVE_MS = 700

export function useTrainingBuilderAutosave(options: {
  persistAllPending: () => Promise<void>
}): {
  flush: () => Promise<void>
  markClean: () => void
  syncState: ReturnType<typeof ref<TrainingBuilderSyncState>>
} {
  const { t } = useLanguage()
  const notify = useNotifications()
  const builder = useTrainingBuilderStore()
  const syncState = ref<TrainingBuilderSyncState>('idle')
  let timer = 0
  let generation = 0
  let lastSaved = ''
  let inflight: Promise<void> | null = null

  function documentKey(): string {
    return trainingCourseFingerprint(builder.title, builder.description, builder.steps)
  }

  function markClean(): void {
    lastSaved = documentKey()
    syncState.value = lastSaved ? 'saved' : 'idle'
  }

  async function persistNow(): Promise<void> {
    if (!builder.courseId || !builder.steps.length) return
    const key = documentKey()
    if (key === lastSaved) return
    const token = (generation += 1)
    syncState.value = 'saving'
    try {
      await options.persistAllPending()
      if (token !== generation) return
      const saved = await saveTrainingCourse(
        builder.courseId,
        trainingCourseWriteBody(builder.title, builder.description, builder.steps)
      )
      if (token !== generation) return
      mergeSavedStepMeta(builder.steps, saved.steps)
      lastSaved = documentKey()
      syncState.value = 'saved'
    } catch (error) {
      if (token !== generation) return
      syncState.value = 'error'
      throw error
    }
  }

  async function flush(): Promise<void> {
    window.clearTimeout(timer)
    if (inflight) {
      await inflight
    }
    inflight = persistNow()
    try {
      await inflight
    } finally {
      inflight = null
    }
  }

  function schedule(): void {
    if (!builder.courseId) return
    if (documentKey() === lastSaved) return
    window.clearTimeout(timer)
    timer = window.setTimeout(() => {
      void flush().catch((error: unknown) => {
        const detail = error instanceof Error ? error.message : ''
        notify.error(detail && detail !== 'save' ? detail : t('training.builder.saveFailed'))
      })
    }, AUTOSAVE_MS)
  }

  watch(
    () => [builder.title, builder.description, builder.steps] as const,
    () => {
      if (!lastSaved) return
      schedule()
    },
    { deep: true }
  )

  function onHidden(): void {
    if (document.visibilityState !== 'hidden') return
    if (documentKey() !== lastSaved) {
      void flush().catch(() => undefined)
    }
  }

  document.addEventListener('visibilitychange', onHidden)
  window.addEventListener('pagehide', onHidden)
  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onHidden)
    window.removeEventListener('pagehide', onHidden)
    window.clearTimeout(timer)
    if (builder.courseId && documentKey() !== lastSaved) {
      void persistNow().catch(() => undefined)
    }
  })

  return {
    flush,
    markClean,
    syncState,
  }
}
