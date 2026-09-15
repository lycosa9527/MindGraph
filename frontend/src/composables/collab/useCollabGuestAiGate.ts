/**
 * Collab AI tools: host may generate; guests see disabled controls + a notice.
 * Owner flag lives on the diagram session (synced from the workshop join).
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramStore } from '@/stores'

export function isCollabGuestAiBlocked(
  collabSessionActive: boolean,
  isDiagramOwner: boolean
): boolean {
  return collabSessionActive && !isDiagramOwner
}

export function useCollabGuestAiGate() {
  const diagramStore = useDiagramStore()
  const notify = useNotifications()
  const { t } = useLanguage()

  const aiBlockedByCollab = computed(() =>
    isCollabGuestAiBlocked(diagramStore.collabSessionActive, diagramStore.collabIsDiagramOwner)
  )

  function notifyCollabGuestAiBlocked(): void {
    notify.warning(t('canvas.toolbar.collabAiBlocked'))
  }

  /** False when a guest must not start an AI tool (notice already shown). */
  function guardCollabGuestAi(): boolean {
    if (!aiBlockedByCollab.value) {
      return true
    }
    notifyCollabGuestAiBlocked()
    return false
  }

  return {
    aiBlockedByCollab,
    notifyCollabGuestAiBlocked,
    guardCollabGuestAi,
  }
}
