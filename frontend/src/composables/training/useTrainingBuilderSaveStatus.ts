/**
 * Course-builder save line, same buckets as the canvas top bar.
 */
import { type ComputedRef, type Ref, computed, onMounted, onUnmounted, ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import type { TrainingBuilderSyncState } from '@/composables/training/useTrainingBuilderAutosave'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import { editorSavedAgo } from '@/utils/editorSavedAgo'

export type TrainingBuilderSaveTone = 'saving' | 'dirty' | 'saved' | 'error'

export function useTrainingBuilderSaveStatus(
  syncState: Ref<TrainingBuilderSyncState>,
  lastSavedAt: Ref<Date | null>,
  isDirty: ComputedRef<boolean>
): {
  saveLabel: ComputedRef<string>
  saveTone: ComputedRef<TrainingBuilderSaveTone>
} {
  const { t, currentLanguage } = useLanguage()
  const builder = useTrainingBuilderStore()
  const tick = ref(0)
  let timer: ReturnType<typeof setInterval> | null = null

  function savedAgo(date: Date): string {
    const ago = editorSavedAgo(date, currentLanguage.value)
    if (ago.key === 'editor.autoSavedAt') return t(ago.key).replace('{time}', ago.time)
    if ('n' in ago) return t(ago.key, { n: ago.n })
    return t(ago.key)
  }

  const saveTone = computed((): TrainingBuilderSaveTone => {
    if (builder.busy || syncState.value === 'saving') return 'saving'
    if (syncState.value === 'error') return 'error'
    if (isDirty.value) return 'dirty'
    return 'saved'
  })

  const saveLabel = computed(() => {
    void tick.value
    if (saveTone.value === 'saving') return t('editor.saving')
    if (saveTone.value === 'error') return t('training.builder.autosaveError')
    if (saveTone.value === 'dirty') return t('editor.unsavedChanges')
    const at = lastSavedAt.value
    return at ? savedAgo(at) : ''
  })

  onMounted(() => {
    timer = setInterval(() => {
      tick.value += 1
    }, 30_000)
  })

  onUnmounted(() => {
    if (!timer) return
    clearInterval(timer)
    timer = null
  })

  return { saveLabel, saveTone }
}
