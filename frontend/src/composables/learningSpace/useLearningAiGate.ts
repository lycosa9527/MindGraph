/**
 * Guard AI affordances when the canvas is in Learning Space homework mode.
 */
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import {
  type LearningAiCapability,
  useLearningAssignmentCanvasStore,
} from '@/stores/learningAssignmentCanvas'

export function useLearningAiGate() {
  const lsCanvas = useLearningAssignmentCanvasStore()
  const notify = useNotifications()
  const { t } = useLanguage()

  function requireCapability(capability: LearningAiCapability): boolean {
    if (lsCanvas.can(capability)) return true
    if (lsCanvas.isActive) {
      notify.warning(t('learningSpace.aiCapabilityBlocked'))
    }
    return false
  }

  return {
    lsCanvas,
    can: lsCanvas.can,
    requireCapability,
  }
}
