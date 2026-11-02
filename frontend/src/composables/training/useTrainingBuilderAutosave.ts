import { type ComputedRef, type Ref, computed, onUnmounted, ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import {
  mergeSavedStepMeta,
  trainingCourseFingerprint,
  trainingCourseWriteBody,
} from '@/composables/training/trainingBuilderSteps'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import { parseApiInstant } from '@/utils/beijingClock'
import { saveTrainingCourse } from '@/utils/trainingApi'

export type TrainingBuilderSyncState = 'idle' | 'saving' | 'saved' | 'error'

const AUTOSAVE_MS = 700

export function useTrainingBuilderAutosave(options: { persistAllPending: () => Promise<void> }): {
  flush: () => Promise<void>
  markClean: (savedAt?: string | null) => void
  syncState: Ref<TrainingBuilderSyncState>
  lastSavedAt: Ref<Date | null>
  isDirty: ComputedRef<boolean>
} {
  const { t } = useLanguage()
  const notify = useNotifications()
  const builder = useTrainingBuilderStore()
  const syncState = ref<TrainingBuilderSyncState>('idle')
  const lastSaved = ref('')
  const lastSavedAt = ref<Date | null>(null)
  let timer = 0
  let generation = 0
  let inflight: Promise<void> | null = null

  function documentKey(): string {
    return trainingCourseFingerprint(builder.title, builder.description, builder.steps)
  }

  const isDirty = computed(() => Boolean(lastSaved.value) && documentKey() !== lastSaved.value)

  function markClean(savedAt?: string | null): void {
    lastSaved.value = documentKey()
    lastSavedAt.value = parseApiInstant(savedAt) ?? new Date()
    syncState.value = lastSaved.value ? 'saved' : 'idle'
  }

  async function persistNow(): Promise<void> {
    if (!builder.courseId || !builder.steps.length) return
    const key = documentKey()
    if (key === lastSaved.value) return
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
      lastSaved.value = documentKey()
      lastSavedAt.value = parseApiInstant(saved.updated_at) ?? new Date()
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
    if (documentKey() === lastSaved.value) return
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
      if (!lastSaved.value) return
      schedule()
    },
    { deep: true }
  )

  function onHidden(): void {
    if (document.visibilityState !== 'hidden') return
    if (documentKey() !== lastSaved.value) {
      void flush().catch(() => undefined)
    }
  }

  document.addEventListener('visibilitychange', onHidden)
  window.addEventListener('pagehide', onHidden)
  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onHidden)
    window.removeEventListener('pagehide', onHidden)
    window.clearTimeout(timer)
    if (builder.courseId && documentKey() !== lastSaved.value) {
      void persistNow().catch(() => undefined)
    }
  })

  return {
    flush,
    markClean,
    syncState,
    lastSavedAt,
    isDirty,
  }
}
