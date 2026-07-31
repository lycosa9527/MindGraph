/**
 * Maite recent practice history — session list with invalidation listener.
 */
import { onScopeDispose, ref } from 'vue'

import { listSessions } from '@/api/maite/inquiry'
import { eventBus } from '@/composables/core/useEventBus'
import { useAuthStore } from '@/stores/auth'
import { useMaiteStore } from '@/stores/maite'

import type { MaitePracticeItem } from '@/types/maite'

function toPracticeItem(session: {
  id: number
  title?: string | null
  status: string
  current_stage: string
  mode?: string
  updated_at: string
  created_at: string
}): MaitePracticeItem {
  return {
    id: session.id,
    title: session.title,
    status: session.status,
    current_stage: session.current_stage,
    mode: session.mode,
    updated_at: session.updated_at,
    created_at: session.created_at,
  }
}

export function useMaitePracticeHistory() {
  const store = useMaiteStore()
  const authStore = useAuthStore()
  const loading = ref(false)
  const errorMessage = ref('')

  async function loadSessions(): Promise<void> {
    // Guest shell is allowed (route has no requiresAuth); skip list until signed in.
    if (!authStore.isAuthenticated) {
      store.setRecentPractice([])
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      const sessions = await listSessions()
      const items = sessions.map(toPracticeItem)
      store.setRecentPractice(items)
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'list_failed'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'practice_history',
      })
    } finally {
      loading.value = false
    }
  }

  const offInvalidate = eventBus.on('maite:practice_invalidate', () => {
    void loadSessions()
  })

  onScopeDispose(() => {
    offInvalidate()
  })

  return {
    loading,
    errorMessage,
    recentPractice: store.recentPractice,
    loadSessions,
  }
}
