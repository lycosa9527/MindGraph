/**
 * Poll admin live performance snapshot (latest values only).
 * Teardown on tab unmount and on Vue Router navigation away (stops interval + aborts fetch).
 */
import { computed, ref, shallowRef, watch } from 'vue'

import { useAdminPolling } from '@/composables/admin/useAdminPolling'
import { useAdminPerformanceLive } from '@/composables/queries'

export const PERFORMANCE_POLL_MS = 2000

export function usePerformanceLive() {
  const fetchError = ref<string | null>(null)
  const latest = shallowRef<Record<string, unknown> | null>(null)
  const awaitingFirstComplete = ref(true)

  const {
    data,
    error,
    isFetching,
    refetch,
  } = useAdminPerformanceLive({
    enabled: false,
    refetchInterval: false,
  })

  const loading = computed(() => awaitingFirstComplete.value && isFetching.value)

  watch(data, (value) => {
    if (value != null) {
      latest.value = value
      fetchError.value = null
      awaitingFirstComplete.value = false
    }
  })

  watch(error, (err) => {
    if (err == null) {
      return
    }
    fetchError.value = err instanceof Error ? err.message : String(err)
    awaitingFirstComplete.value = false
  })

  const { refetch: pollRefetch } = useAdminPolling({
    pollKey: 'performance',
    intervalMs: PERFORMANCE_POLL_MS,
    fetch: async () => {
      await refetch()
    },
  })

  return {
    loading,
    fetchError,
    latest,
    refetch: pollRefetch,
  }
}
