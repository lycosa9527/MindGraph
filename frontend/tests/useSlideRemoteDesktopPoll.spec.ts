import { createApp, defineComponent } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useSlideRemoteDesktopPoll } from '@/composables/mindMap/useSlideRemoteDesktopPoll'
import { peekSlideRemotePendingStart } from '@/utils/slideRemotePendingStart'

const drainMock = vi.hoisted(() => vi.fn().mockResolvedValue([]))
const pushMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined))
const routePath = vi.hoisted(() => ({ value: '/mindmate' }))
const authState = vi.hoisted(() => ({
  isAuthenticated: true,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: (...args: unknown[]) => pushMock(...args),
  }),
  useRoute: () => ({
    path: routePath.value,
    meta: {},
  }),
}))

vi.mock('@/utils/slideRemoteApi', () => ({
  drainSlideRemoteCommands: (...args: unknown[]) => drainMock(...args),
}))

vi.mock('pinia', async () => {
  const actual = await vi.importActual<typeof import('pinia')>('pinia')
  return {
    ...actual,
    storeToRefs: (store: { isAuthenticated: boolean }) => ({
      isAuthenticated: { value: store.isAuthenticated },
    }),
  }
})

function mountPoll() {
  const app = createApp(
    defineComponent({
      setup() {
        useSlideRemoteDesktopPoll()
        return () => null
      },
    })
  )
  app.mount(document.createElement('div'))
  return () => app.unmount()
}

describe('useSlideRemoteDesktopPoll', () => {
  beforeEach(() => {
    sessionStorage.clear()
    localStorage.clear()
    routePath.value = '/mindmate'
    authState.isAuthenticated = true
    drainMock.mockReset()
    drainMock.mockResolvedValue([])
    pushMock.mockReset()
    pushMock.mockResolvedValue(undefined)
  })

  afterEach(() => {
    sessionStorage.clear()
    localStorage.clear()
  })

  it('jumps from a non-canvas page when Start names a diagram', async () => {
    drainMock.mockResolvedValueOnce([{ action: 'start', diagram_id: 'diag-9' }])
    const stop = mountPoll()
    await vi.waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith({ path: '/canvas', query: { diagramId: 'diag-9' } })
    })
    expect(peekSlideRemotePendingStart()).toBe('diag-9')
    stop()
  })

  it('does not drain while the canvas editor is open', async () => {
    routePath.value = '/canvas'
    drainMock.mockResolvedValueOnce([{ action: 'start', diagram_id: 'diag-9' }])
    const stop = mountPoll()
    await new Promise((resolve) => {
      setTimeout(resolve, 50)
    })
    expect(drainMock).not.toHaveBeenCalled()
    expect(pushMock).not.toHaveBeenCalled()
    stop()
  })
})
