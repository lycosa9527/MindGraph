/**
 * runKittyEditTurn: hub fail blocks text send; success sends text.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'

const { syncKittyHubContextMock } = vi.hoisted(() => ({
  syncKittyHubContextMock: vi.fn(),
}))

vi.mock('@/composables/kitty/syncKittyHubContext', () => ({
  syncKittyHubContext: syncKittyHubContextMock,
  KITTY_HUB_EDIT_GATE_TIMEOUT_MS: 8000,
  KITTY_HUB_BACKGROUND_SYNC_TIMEOUT_MS: 3000,
}))

vi.mock('@/composables/core/useEventBus', () => ({
  eventBus: {
    emit: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    onWithOwner: vi.fn(),
    removeAllListenersForOwner: vi.fn(),
  },
}))

vi.mock('@/composables/kitty/kittyAgentDebug', () => ({
  normalizeKittyDebugText: (s: string) => s,
}))

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    type: 'mindmap',
    data: { nodes: [{ id: 't', text: 'T' }], connections: [] },
  }),
}))

vi.mock('@/composables/kitty/kittyDiagramFingerprint', () => ({
  getKittyDiagramContentFingerprint: () => 'fp-1',
}))

import { runKittyEditTurn } from '@/composables/kitty/pipeline/editTurn'
import { getLastFail } from '@/composables/kitty/pipeline/trace'

describe('runKittyEditTurn', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    syncKittyHubContextMock.mockReset()
  })

  it('does not send text when hub sync fails', async () => {
    syncKittyHubContextMock.mockResolvedValue({ ok: false, error: 'hub_persist_timeout' })
    const sendTextMessage = vi.fn(() => true)
    const onFailMessage = vi.fn()
    const kitty = {
      sendTextMessage,
      updateContext: vi.fn(),
      isConnected: ref(true),
      isLiveForScope: () => true,
      reconcileLiveState: vi.fn(),
      startConversation: vi.fn(),
    }

    const result = await runKittyEditTurn(
      {
        kitty: kitty as never,
        buildContext: () =>
          ({
            diagram_type: 'mindmap',
            active_panel: 'none',
            selected_nodes: [],
            diagram_data: {},
          }) as never,
        updateContext: kitty.updateContext,
        getScope: () => 'scope-1',
        lane: 'mobile',
        ensureConnected: async () => true,
        appendUserTurn: async () => true,
        onFailMessage,
        t: (_k, fb) => fb ?? _k,
      },
      { text: '添加分支', source: 'asr', requestId: 'req-hub-fail' }
    )

    expect(result.ok).toBe(false)
    expect(result.sent).toBe(false)
    expect(sendTextMessage).not.toHaveBeenCalled()
    expect(getLastFail()?.step).toBe('S07_hub_sync')
    expect(onFailMessage).toHaveBeenCalled()
  })

  it('sends text after successful hub sync', async () => {
    syncKittyHubContextMock.mockResolvedValue({ ok: true, revision: 4 })
    const sendTextMessage = vi.fn(() => true)
    const kitty = {
      sendTextMessage,
      updateContext: vi.fn(),
      isConnected: ref(true),
      isLiveForScope: () => true,
      reconcileLiveState: vi.fn(),
      startConversation: vi.fn(),
    }

    const result = await runKittyEditTurn(
      {
        kitty: kitty as never,
        buildContext: () =>
          ({
            diagram_type: 'mindmap',
            active_panel: 'none',
            selected_nodes: [],
            diagram_data: {},
          }) as never,
        updateContext: kitty.updateContext,
        getScope: () => 'scope-1',
        lane: 'mobile',
        ensureConnected: async () => true,
        appendUserTurn: async () => true,
        onFailMessage: vi.fn(),
        t: (_k, fb) => fb ?? _k,
      },
      { text: '添加广东分支', source: 'text', requestId: 'req-ok' }
    )

    expect(result.ok).toBe(true)
    expect(result.sent).toBe(true)
    expect(sendTextMessage).toHaveBeenCalledWith('添加广东分支', 'req-ok')
  })
})
