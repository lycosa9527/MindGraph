/**
 * Open a saved seminar transcript from `/mindmate?saved_seminar=`.
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { leaveSavedMindmateSeminar } from '@/utils/mindmateCollabLibrarySave'

export function useMindmateSavedSeminar() {
  const route = useRoute()

  const sessionId = computed(() => {
    const raw = route.query.saved_seminar
    return typeof raw === 'string' && raw.trim() ? raw.trim() : null
  })

  function clear(): void {
    leaveSavedMindmateSeminar()
  }

  return { sessionId, clear }
}
