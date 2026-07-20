import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { effectScope, nextTick, ref } from 'vue'
import { createApp } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { apiRequest, apiRequestJson } = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  apiRequestJson: vi.fn(),
}))

vi.mock('@/utils/apiClient', () => ({
  apiRequest: (...args: unknown[]) => apiRequest(...args),
  apiRequestJson: (...args: unknown[]) => apiRequestJson(...args),
}))

import { useChatHandoff } from '@/composables/mindMap/useChatHandoff'

function withQueryApp<T>(run: () => T): { result: T; stop: () => void } {
  const app = createApp({ render: () => null })
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  app.use(VueQueryPlugin, { queryClient: client })
  const scope = effectScope(true)
  let result!: T
  app.runWithContext(() => {
    scope.run(() => {
      result = run()
    })
  })
  return {
    result,
    stop: () => {
      scope.stop()
    },
  }
}

describe('useChatHandoff', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    apiRequestJson.mockReset()
    apiRequest.mockResolvedValue({ ok: true })
    apiRequestJson.mockResolvedValue({
      code: '123456',
      expires_in_seconds: 600,
      package_id: 3,
      status: 'waiting',
      document_id: null,
    })
  })

  it('revokes the waiting pairing code when the composable scope is disposed', async () => {
    const packageId = ref<number | null>(3)
    const { result, stop } = withQueryApp(() => useChatHandoff(packageId))

    const code = await result.mintPairingCode()
    expect(code).toBe('123456')
    expect(result.handoffStatus.value).toBe('waiting')

    stop()
    await nextTick()

    expect(apiRequest).toHaveBeenCalledWith(
      '/api/doc-summary/chat-handoff/cancel',
      expect.objectContaining({
        method: 'POST',
        keepalive: true,
        body: JSON.stringify({ code: '123456', package_id: 3 }),
      })
    )
  })

  it('revokes the prior package pairing when package id changes', async () => {
    const packageId = ref<number | null>(3)
    const { result, stop } = withQueryApp(() => useChatHandoff(packageId))

    await result.mintPairingCode()
    apiRequest.mockClear()

    packageId.value = null
    await nextTick()

    expect(apiRequest).toHaveBeenCalledWith(
      '/api/doc-summary/chat-handoff/cancel',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ code: '123456', package_id: 3 }),
      })
    )
    stop()
  })
})
