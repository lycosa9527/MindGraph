import { type MaybeRef, onScopeDispose, ref, unref, watch } from 'vue'

import { useQueryClient } from '@tanstack/vue-query'

import { fileCenterKeys } from '@/composables/fileCenter/useFileCenter'
import { DOC_SUMMARY_CHAT_HANDOFF_BASE } from '@/config/docSummaryApi'
import { apiRequest, apiRequestJson } from '@/utils/apiClient'

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

function fireRevokeHandoff(code: string | null, packageId: number | null): void {
  if (!code && packageId === null) {
    return
  }
  const body: { code?: string; package_id?: number } = {}
  if (code) {
    body.code = code
  }
  if (packageId !== null) {
    body.package_id = packageId
  }
  void apiRequest(`${DOC_SUMMARY_CHAT_HANDOFF_BASE}/cancel`, {
    method: 'POST',
    body: JSON.stringify(body),
    keepalive: true,
  }).catch(() => undefined)
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
        `${DOC_SUMMARY_CHAT_HANDOFF_BASE}/status?code=${encodeURIComponent(code)}`
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

  function resetHandoff(options?: {
    revoke?: boolean
    packageIdForRevoke?: number | null
  }): void {
    const code = pairingCode.value
    const status = handoffStatus.value
    const packageIdForRevoke = options?.packageIdForRevoke ?? unref(packageId)
    // Keep in-flight ingest (claimed / indexing); revoke unused or expired waits.
    const claimedOrFinished =
      status === 'received'
      || status === 'indexing'
      || status === 'done'
      || status === 'failed'
    const shouldRevoke =
      options?.revoke !== false && Boolean(code) && !claimedOrFinished

    stopPolling()
    pairingCode.value = null
    handoffStatus.value = 'idle'
    mintError.value = null

    if (shouldRevoke && code) {
      fireRevokeHandoff(code, packageIdForRevoke)
    }
  }

  async function mintPairingCode(): Promise<string | null> {
    const id = unref(packageId)
    if (id === null || isMinting.value) {
      return null
    }
    isMinting.value = true
    mintError.value = null
    try {
      if (pairingCode.value) {
        fireRevokeHandoff(pairingCode.value, id)
        pairingCode.value = null
        stopPolling()
      }
      const response = await apiRequestJson<HandoffStartResponse>(
        `${DOC_SUMMARY_CHAT_HANDOFF_BASE}/start`,
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

  watch(
    () => unref(packageId),
    (_next, previous) => {
      resetHandoff({
        packageIdForRevoke: previous ?? null,
      })
    }
  )

  onScopeDispose(() => {
    resetHandoff()
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
