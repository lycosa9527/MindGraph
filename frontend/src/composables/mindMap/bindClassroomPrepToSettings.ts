/**
 * Drop parked 思维讲堂 scripts when launch settings or audience change.
 */
import { watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import {
  cancelMindClassroomJob,
  isClassroomJobActive,
} from '@/composables/mindMap/mindClassroomJobApi'
import { useLanguage } from '@/composables/core/useLanguage'
import { useAiContentLevelStore, useMindClassroomStore } from '@/stores'

export function bindClassroomPrepToSettings(): void {
  const classroomStore = useMindClassroomStore()
  const aiLevelStore = useAiContentLevelStore()
  const { currentLanguage } = useLanguage()
  watch(
    () =>
      [
        classroomStore.mastery,
        classroomStore.presentation,
        classroomStore.tourScope,
        classroomStore.slideStyle,
        classroomStore.tone,
        aiLevelStore.level,
        currentLanguage.value,
      ] as const,
    () => {
      void invalidatePreparedForSettingsChange()
    }
  )
}

async function invalidatePreparedForSettingsChange(): Promise<void> {
  const classroomStore = useMindClassroomStore()
  if (classroomStore.isLecturing) return
  const rows = classroomStore.listPreparedJobs()
  if (!rows.length && !classroomStore.preparedSteps.length) return
  classroomStore.clearAllPrepared()
  await Promise.all(
    rows
      .filter((row) => isClassroomJobActive(row.status))
      .map(async (row) => {
        try {
          await cancelMindClassroomJob(row.id)
        } catch {
          /* already gone */
        }
      })
  )
  if (classroomStore.isLaunchActive) {
    eventBus.emit('classroom:restore_prepared_requested', {})
  }
}
