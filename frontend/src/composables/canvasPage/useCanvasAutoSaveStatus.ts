/**
 * Shared auto-save status text for canvas pages (desktop top bar, mobile toolbar).
 */
import { type ComputedRef, type Ref, computed, onMounted, onUnmounted, ref } from 'vue'

import type { LocaleCode } from '@/i18n/locales'
import { intlLocaleForUiCode } from '@/i18n/locales'

import { useLanguage } from '../core/useLanguage'
import type { useDiagramAutoSave } from '../editor/useDiagramAutoSave'

type DiagramAutoSave = ReturnType<typeof useDiagramAutoSave>

export interface UseCanvasAutoSaveStatusOptions {
  diagramAutoSave: DiagramAutoSave
  isAuthenticated: ComputedRef<boolean> | Ref<boolean>
  isSlotsFullyUsed: ComputedRef<boolean> | Ref<boolean>
  activeDiagramId: ComputedRef<string | null> | Ref<string | null>
}

export function useCanvasAutoSaveStatus(options: UseCanvasAutoSaveStatusOptions): {
  autoSavedStatusText: ComputedRef<string | null>
} {
  const { diagramAutoSave, isAuthenticated, isSlotsFullyUsed, activeDiagramId } = options
  const { t, currentLanguage } = useLanguage()
  const relativeTimeTick = ref(0)
  let relativeTimeInterval: ReturnType<typeof setInterval> | null = null

  function formatRelativeTime(date: Date): string {
    void relativeTimeTick.value
    const diffMs = Date.now() - date.getTime()
    const diffSec = Math.floor(diffMs / 1000)
    if (diffSec < 10) return t('editor.savedJustNow')
    if (diffSec < 60) return t('editor.savedSecondsAgo', { n: diffSec })
    const diffMin = Math.floor(diffSec / 60)
    if (diffMin < 60) return t('editor.savedMinutesAgo', { n: diffMin })
    const timeStr = date.toLocaleTimeString(
      intlLocaleForUiCode(currentLanguage.value as LocaleCode),
      {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }
    )
    return t('editor.autoSavedAt').replace('{time}', timeStr)
  }

  const autoSavedStatusText = computed(() => {
    if (!isAuthenticated.value) return null
    if (isSlotsFullyUsed.value && !activeDiagramId.value) {
      return t('editor.slotsFull')
    }
    if (diagramAutoSave.isSaving.value) return t('editor.saving')
    const at = diagramAutoSave.lastSavedAt.value
    if (!at) {
      if (diagramAutoSave.isDirty.value) return t('editor.unsavedChanges')
      return null
    }
    if (diagramAutoSave.isDirty.value) return t('editor.unsavedChanges')
    return formatRelativeTime(at)
  })

  onMounted(() => {
    relativeTimeInterval = setInterval(() => {
      relativeTimeTick.value += 1
    }, 30_000)
  })

  onUnmounted(() => {
    if (relativeTimeInterval) {
      clearInterval(relativeTimeInterval)
      relativeTimeInterval = null
    }
  })

  return { autoSavedStatusText }
}
