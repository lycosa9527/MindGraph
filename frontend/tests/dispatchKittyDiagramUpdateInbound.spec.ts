/**
 * Thin mobile inbound: chat summary only; desktop emits mutation bus.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { emitMock } = vi.hoisted(() => ({
  emitMock: vi.fn(),
}))

vi.mock('@/composables/core/useEventBus', () => ({
  eventBus: {
    emit: emitMock,
    on: vi.fn(),
    off: vi.fn(),
    onWithOwner: vi.fn(),
    removeAllListenersForOwner: vi.fn(),
  },
}))

vi.mock('@/composables/kitty/applyKittyRemoteLlmModel', () => ({
  applyKittyRemoteLlmModel: vi.fn(),
}))

vi.mock('@/composables/kitty/kittyAgentActions', () => ({
  executeKittyAgentAction: vi.fn(),
}))

vi.mock('@/composables/kitty/kittySelectionApply', () => ({
  applyKittyRemoteCanvasSelection: vi.fn(),
}))

vi.mock('@/composables/kitty/kittyWorkflowTrace', () => ({
  traceKittyWorkflow: vi.fn(),
}))

import { dispatchKittyDiagramUpdateInbound } from '@/composables/kitty/kittyAgentInbound'

describe('dispatchKittyDiagramUpdateInbound', () => {
  beforeEach(() => {
    emitMock.mockClear()
  })

  it('mobile lane emits chat reply and does not request mutation apply', () => {
    dispatchKittyDiagramUpdateInbound(
      {
        action: 'add_child_node',
        updates: { text: 'x' },
        mutation_id: 'mut-9',
        user_summary: '已添加',
      },
      { clientLane: 'mobile' }
    )

    expect(emitMock).toHaveBeenCalledWith(
      'kitty:one_sentence_reply',
      expect.objectContaining({ text: '已添加', kind: 'final' })
    )
    expect(
      emitMock.mock.calls.some((c) => c[0] === 'kitty:diagram_mutation_requested')
    ).toBe(false)
  })

  it('desktop lane emits mutation bus with hubPersist when builders present', () => {
    const sendAck = vi.fn()
    const buildContext = vi.fn()
    const updateContext = vi.fn()
    dispatchKittyDiagramUpdateInbound(
      {
        action: 'add_child_node',
        updates: { text: 'x' },
        mutation_id: 'mut-9',
        user_summary: '已添加',
      },
      {
        clientLane: 'desktop',
        sendDiagramMutationAck: sendAck,
        buildDiagramContext: buildContext,
        updateContext,
        diagramSessionId: 'lib-1',
      }
    )

    expect(emitMock).toHaveBeenCalledWith(
      'kitty:diagram_mutation_requested',
      expect.objectContaining({
        action: 'add_child_node',
        mutationId: 'mut-9',
        lane: 'desktop',
        sendAck,
        hubPersist: expect.objectContaining({ scope: 'lib-1' }),
      })
    )
  })
})
