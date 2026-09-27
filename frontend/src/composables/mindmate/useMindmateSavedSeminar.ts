/**
 * Open a saved seminar transcript from `/mindmate?saved_seminar=`.
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export function useMindmateSavedSeminar() {
  const route = useRoute()
  const router = useRouter()

  const sessionId = computed(() => {
    const raw = route.query.saved_seminar
    return typeof raw === 'string' && raw.trim() ? raw.trim() : null
  })

  function clear(): void {
    if (typeof route.query.saved_seminar !== 'string') {
      return
    }
    const nextQuery = { ...route.query }
    delete nextQuery.saved_seminar
    void router.replace({ query: nextQuery })
  }

  return { sessionId, clear }
}
