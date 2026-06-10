/**
 * Warn when leaving canvas with unsaved diagram changes (route + tab close).
 */
import { onBeforeRouteLeave } from 'vue-router'
import { onMounted, onUnmounted, type Ref } from 'vue'

import { useLanguage } from '../core/useLanguage'

export interface UseCanvasUnsavedLeaveGuardOptions {
  isDirty: Ref<boolean>
  /** When true, navigation proceeds without confirmation. */
  shouldBypassLeaveConfirm?: () => boolean
}

export function useCanvasUnsavedLeaveGuard(
  options: UseCanvasUnsavedLeaveGuardOptions
): void {
  const { isDirty, shouldBypassLeaveConfirm } = options
  const { t } = useLanguage()

  function confirmLeaveIfDirty(): boolean {
    if (shouldBypassLeaveConfirm?.()) {
      return true
    }
    if (!isDirty.value) {
      return true
    }
    return window.confirm(t('editor.unsavedChanges'))
  }

  function onBeforeUnload(event: BeforeUnloadEvent): void {
    if (shouldBypassLeaveConfirm?.()) {
      return
    }
    if (!isDirty.value) {
      return
    }
    event.preventDefault()
    event.returnValue = ''
  }

  onBeforeRouteLeave(() => {
    if (!confirmLeaveIfDirty()) {
      return false
    }
    return true
  })

  onMounted(() => {
    window.addEventListener('beforeunload', onBeforeUnload)
  })

  onUnmounted(() => {
    window.removeEventListener('beforeunload', onBeforeUnload)
  })
}
