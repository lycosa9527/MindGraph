import { type MaybeRef, onScopeDispose, ref, unref, watch } from 'vue'

import { useQueryClient } from '@tanstack/vue-query'

import { fileCenterKeys } from '@/composables/fileCenter/useFileCenter'
import { apiRequestJson } from '@/utils/apiClient'

type HandoffStatusResponse = {
  code: string
  status: string
  package_id: number
  document_id: number | null
}

type HandoffStartResponse = {
  code: string
  expires_in_seconds: number
  package_id: number
}

export function useChatHandoff(packageId: MaybeRef<number | null>) {
  const queryClient = useQueryClient()
  const pairingCode = ref<string | null>(null)
  const handoffStatus = ref<string>('idle')
  const expiresInSeconds = ref<number>(600)
  const isMinting = ref(false)
  const mintError = ref<string | null>(null)

  let pollTimer: ReturnType<typeof setInterval> | null = null

  function stopPolling(): void {
    if (pollTimer !== null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function invalidatePackageDetail(packageIdValue: number): void {
    void queryClient.invalidateQueries({ queryKey: fileCenterKeys.package(packageIdValue) })
  }

  async function pollStatus(code: string): Promise<void> {
    try {
      const status = await apiRequestJson<HandoffStatusResponse>(
        `/api/knowledge-space/chat-handoff/status?code=${encodeURIComponent(code)}`
      )
      handoffStatus.value = status.status
      if (status.status === 'done' || status.status === 'failed') {
        stopPolling()
        invalidatePackageDetail(status.package_id)
      }
    } catch {
      stopPolling()
      if (
        handoffStatus.value === 'waiting'
        || handoffStatus.value === 'received'
        || handoffStatus.value === 'indexing'
      ) {
        handoffStatus.value = 'expired'
      }
    }
  }

  function startPolling(code: string): void {
    stopPolling()
    handoffStatus.value = 'waiting'
    void pollStatus(code)
    pollTimer = setInterval(() => {
      void pollStatus(code)
    }, 1500)
  }

  async function mintPairingCode(): Promise<string | null> {
    const id = unref(packageId)
    if (id === null || isMinting.value) {
      return null
    }
    isMinting.value = true
    mintError.value = null
    try {
      const response = await apiRequestJson<HandoffStartResponse>(
        '/api/knowledge-space/chat-handoff/start',
        {
          method: 'POST',
          body: JSON.stringify({ package_id: id }),
        }
      )
      pairingCode.value = response.code
      expiresInSeconds.value = response.expires_in_seconds
      startPolling(response.code)
      return response.code
    } catch (error) {
      mintError.value = error instanceof Error ? error.message : 'mint failed'
      return null
    } finally {
      isMinting.value = false
    }
  }

  function resetHandoff(): void {
    stopPolling()
    pairingCode.value = null
    handoffStatus.value = 'idle'
    mintError.value = null
  }

  watch(
    () => unref(packageId),
    () => {
      resetHandoff()
    }
  )

  onScopeDispose(() => {
    stopPolling()
  })

  return {
    pairingCode,
    handoffStatus,
    expiresInSeconds,
    isMinting,
    mintError,
    mintPairingCode,
    resetHandoff,
  }
}
