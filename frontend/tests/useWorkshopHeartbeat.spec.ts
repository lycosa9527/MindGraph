import { describe, expect, it, vi } from 'vitest'
import { nextTick, ref } from 'vue'

import { useWorkshopHeartbeat } from '@/composables/workshop/useWorkshopHeartbeat'

describe('useWorkshopHeartbeat', () => {
  it('closes socket when pong deadline fires', async () => {
    vi.useFakeTimers()
    const ws = ref<WebSocket | null>(null)
    const connected = ref(true)
    const { startHeartbeat, stopHeartbeat } = useWorkshopHeartbeat(ws, connected)

    const close = vi.fn()
    const send = vi.fn()
    ws.value = {
      readyState: WebSocket.OPEN,
      send,
      close,
    } as unknown as WebSocket

    startHeartbeat()
    expect(send).toHaveBeenCalled()
    vi.advanceTimersByTime(10_000)
    await nextTick()
    expect(close).toHaveBeenCalledWith(4000, 'pong_timeout')
    stopHeartbeat()
    vi.useRealTimers()
  })
})
