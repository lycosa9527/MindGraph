import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Ref } from 'vue'

export interface Watch {
  id: string
  watch_id: string
  student_id?: number
  student_name?: string
  status: 'unassigned' | 'assigned' | 'connected' | 'learning_mode' | 'offline'
  last_seen?: string
  battery_level?: number
}

export interface SmartResponseSession {
  id: string
  diagram_id: string
  watch_ids: string[]
  created_at: string
}

export const useSmartResponseStore = defineStore('smartResponse', () => {
  const watches: Ref<Watch[]> = ref([])
  const currentSession: Ref<SmartResponseSession | null> = ref(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const unassignedWatches = computed(() => 
    watches.value.filter(w => w.status === 'unassigned')
  )

  const assignedWatches = computed(() => 
    watches.value.filter(w => w.status === 'assigned' || w.status === 'connected')
  )

  const connectedWatches = computed(() => 
    watches.value.filter(w => w.status === 'connected' || w.status === 'learning_mode')
  )

  async function fetchWatches() {
    isLoading.value = true
    error.value = null
    try {
      const response = await fetch('/api/devices')
      if (!response.ok) throw new Error('Failed to fetch watches')
      watches.value = await response.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      isLoading.value = false
    }
  }

  async function assignWatch(watchId: string, studentId: number) {
    isLoading.value = true
    error.value = null
    try {
      const response = await fetch(`/api/devices/${watchId}/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: studentId }),
      })
      if (!response.ok) throw new Error('Failed to assign watch')
      await fetchWatches()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      isLoading.value = false
    }
  }

  async function startLearningMode(diagramId: string, watchIds?: string[]) {
    isLoading.value = true
    error.value = null
    try {
      const sessionId = `session_${Date.now()}`
      currentSession.value = {
        id: sessionId,
        diagram_id: diagramId,
        watch_ids: watchIds || [],
        created_at: new Date().toISOString(),
      }
      // WebSocket will handle the actual broadcast
      return sessionId
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      return null
    } finally {
      isLoading.value = false
    }
  }

  function reset(): void {
    watches.value = []
    currentSession.value = null
    isLoading.value = false
    error.value = null
  }

  return {
    watches,
    currentSession,
    isLoading,
    error,
    unassignedWatches,
    assignedWatches,
    connectedWatches,
    fetchWatches,
    assignWatch,
    startLearningMode,
    reset,
  }
})