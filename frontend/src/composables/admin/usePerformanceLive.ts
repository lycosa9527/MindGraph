/**
 * Poll admin live performance snapshot (latest values only; no chart buffers).
 * Teardown on tab unmount and on Vue Router navigation away (stops interval + aborts fetch).
 */
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

import { apiRequest } from '@/utils/apiClient'

export const PERFORMANCE_POLL_MS = 2000

function _isAbortError(e: unknown): boolean {
  if (e instanceof DOMException && e.name === 'AbortError') {
    return true
  }
  return e instanceof Error && e.name === 'AbortError'
}

export function usePerformanceLive() {
  const loading = ref(false)
  const fetchError = ref<string | null>(null)
  const latest = shallowRef<Record<string, unknown> | null>(null)

  let intervalId: ReturnType<typeof setInterval> | null = null
  /** Only the first in-flight request should drive full-panel `v-loading` (avoids flash every poll). */
  let awaitingFirstComplete = true
  let tearDown = false
  let fetchAbort: AbortController | null = null

  function stopPolling(): void {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  function dispose(): void {
    if (tearDown) {
      return
    }
    tearDown = true
    document.removeEventListener('visibilitychange', onVisibility)
    stopPolling()
    fetchAbort?.abort()
    fetchAbort = null
  }

  async function fetchOnce(): Promise<void> {
    if (tearDown) {
      return
    }
    fetchAbort?.abort()
    fetchAbort = new AbortController()
    const signal = fetchAbort.signal
    if (awaitingFirstComplete) {
      loading.value = true
    }
    fetchError.value = null
    try {
      const res = await apiRequest('/api/auth/admin/performance/live', { signal })
      if (tearDown) {
        return
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const detail = (body as { detail?: string }).detail
        fetchError.value = typeof detail === 'string' ? detail : `HTTP ${res.status}`
        return
      }
      latest.value = (await res.json()) as Record<string, unknown>
    } catch (e) {
      if (tearDown || _isAbortError(e)) {
        return
      }
      fetchError.value = e instanceof Error ? e.message : String(e)
    } finally {
      if (awaitingFirstComplete) {
        loading.value = false
        awaitingFirstComplete = false
      }
    }
  }

  function onVisibility(): void {
    if (document.visibilityState === 'visible') {
      void fetchOnce()
    }
  }

  function startPolling(): void {
    stopPolling()
    void fetchOnce()
    intervalId = setInterval(() => {
      if (document.visibilityState === 'hidden') {
        return
      }
      void fetchOnce()
    }, PERFORMANCE_POLL_MS)
  }

  onMounted(() => {
    startPolling()
    document.addEventListener('visibilitychange', onVisibility)
  })

  onBeforeRouteLeave(() => {
    dispose()
  })

  onBeforeUnmount(() => {
    dispose()
  })

  return {
    loading,
    fetchError,
    latest,
    refetch: fetchOnce,
  }
}
