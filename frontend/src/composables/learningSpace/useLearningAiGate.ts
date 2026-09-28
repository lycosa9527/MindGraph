/**
 * Guard AI affordances when the canvas is in Learning Space homework mode.
 */
import { useNotifications } from '@/composables/core/useNotifications'
import {
  type LearningAiCapability,
  useLearningAssignmentCanvasStore,
} from '@/stores/learningAssignmentCanvas'

export function useLearningAiGate() {
  const lsCanvas = useLearningAssignmentCanvasStore()
  const notify = useNotifications()

  function requireCapability(capability: LearningAiCapability): boolean {
    if (lsCanvas.can(capability)) return true
    if (lsCanvas.isActive) {
      notify.warningKey('learningSpace.aiCapabilityBlocked')
    }
    return false
  }

  return {
    lsCanvas,
    can: lsCanvas.can,
    requireCapability,
  }
}
