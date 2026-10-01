/**
 * Guard AI affordances when the canvas is in Learning Space homework mode.
 *
 * Students on MindGraph library / free canvas get manual editing only; AI is
 * available only on homework canvas when the teacher enabled ``ai_assist``.
 */
import { computed } from 'vue'

import { useNotifications } from '@/composables/core/useNotifications'
import {
  type LearningAiCapability,
  useLearningAssignmentCanvasStore,
} from '@/stores/learningAssignmentCanvas'
import { useAuthStore } from '@/stores/auth'

export function useLearningAiGate() {
  const lsCanvas = useLearningAssignmentCanvasStore()
  const authStore = useAuthStore()
  const notify = useNotifications()

  /** Student opened MindGraph outside Learning Space homework. */
  const studentManualEditOnly = computed(
    () => authStore.user?.role === 'student' && !lsCanvas.isActive
  )

  /** Show AI ribbon entries, model selector, and generate affordances. */
  const showCanvasAiFeatures = computed(() => {
    if (authStore.user?.role !== 'student') {
      return true
    }
    if (!lsCanvas.isActive) {
      return false
    }
    return lsCanvas.aiAssistOn
  })

  function can(capability: LearningAiCapability): boolean {
    if (studentManualEditOnly.value) {
      return false
    }
    return lsCanvas.can(capability)
  }

  function requireCapability(capability: LearningAiCapability): boolean {
    if (studentManualEditOnly.value) {
      return false
    }
    if (lsCanvas.can(capability)) {
      return true
    }
    if (lsCanvas.isActive) {
      notify.warningKey('learningSpace.aiCapabilityBlocked')
    }
    return false
  }

  return {
    lsCanvas,
    studentManualEditOnly,
    showCanvasAiFeatures,
    can,
    requireCapability,
  }
}
