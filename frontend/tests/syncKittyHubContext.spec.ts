/**
 * Shared Kitty hub context sync (desktop + mobile pre-edit gate).
 */
import { describe, expect, it, vi } from 'vitest'

import {
  KITTY_HUB_EDIT_GATE_TIMEOUT_MS,
  syncKittyHubContext,
} from '@/composables/kitty/syncKittyHubContext'

const { persistVerifiedDiagramToHubMock } = vi.hoisted(() => ({
  persistVerifiedDiagramToHubMock: vi.fn(async () => ({ ok: true, revision: 5 })),
}))

vi.mock('@/composables/kitty/diagramEditHubPersist', () => ({
  persistVerifiedDiagramToHub: persistVerifiedDiagramToHubMock,
}))

describe('syncKittyHubContext', () => {
  it('returns not_connected without sending when WS is down', async () => {
    const updateContext = vi.fn()
    const setHubScopeRevision = vi.fn()

    const result = await syncKittyHubContext({
      buildContext: () => ({
        diagram_type: 'mindmap',
        active_panel: 'none',
        selected_nodes: [],
        diagram_data: {},
      }),
      updateContext,
      hubScopeRevision: 2,
      setHubScopeRevision,
      scope: 'scope-1',
      isConnected: false,
      debugLabel: 'edit gate',
    })

    expect(result).toEqual({ ok: false, error: 'not_connected' })
    expect(persistVerifiedDiagramToHubMock).not.toHaveBeenCalled()
    expect(setHubScopeRevision).not.toHaveBeenCalled()
  })

  it('persists context and updates revision on success', async () => {
    persistVerifiedDiagramToHubMock.mockResolvedValueOnce({ ok: true, revision: 7 })
    const updateContext = vi.fn()
    const setHubScopeRevision = vi.fn()
    const buildContext = vi.fn(() => ({
      diagram_type: 'mindmap',
      active_panel: 'one_sentence',
      selected_nodes: [],
      diagram_data: { nodes: [] },
    }))

    const result = await syncKittyHubContext({
      buildContext,
      updateContext,
      hubScopeRevision: 6,
      setHubScopeRevision,
      scope: 'lib-abc',
      isConnected: true,
      timeoutMs: KITTY_HUB_EDIT_GATE_TIMEOUT_MS,
      debugLabel: 'edit gate',
    })

    expect(result).toEqual({ ok: true, revision: 7 })
    expect(persistVerifiedDiagramToHubMock).toHaveBeenCalledWith(
      expect.objectContaining({
        hubScopeRevision: 6,
        scope: 'lib-abc',
        timeoutMs: KITTY_HUB_EDIT_GATE_TIMEOUT_MS,
      })
    )
    expect(setHubScopeRevision).toHaveBeenCalledWith(7)
  })
})
