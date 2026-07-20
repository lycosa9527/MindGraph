/**
 * Verified Kitty mutations must nack during live collab (not silent-drop / ack_timeout).
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { emitMock, applyVerifiedMock, reportFailMock, collabActive, diagramType, onHandlers } =
  vi.hoisted(() => ({
    emitMock: vi.fn(),
    applyVerifiedMock: vi.fn(),
    reportFailMock: vi.fn(),
    collabActive: { value: true },
    diagramType: { value: 'mindmap' as string },
    onHandlers: new Map<string, (payload: unknown) => void>(),
  }))

vi.mock('@/composables/core/useEventBus', () => ({
  eventBus: {
    emit: emitMock,
    on: (event: string, handler: (payload: unknown) => void) => {
      onHandlers.set(event, handler)
    },
    off: (event: string) => {
      onHandlers.delete(event)
    },
    onWithOwner: vi.fn(),
    removeAllListenersForOwner: vi.fn(),
  },
}))

vi.mock('@/composables/kitty/diagramEditApply', () => ({
  applyVerifiedDiagramUpdate: applyVerifiedMock,
}))

vi.mock('@/composables/kitty/kittyAgentActions', () => ({
  applyKittyDiagramUpdate: vi.fn(),
}))

vi.mock('@/composables/kitty/kittyDiagramEditFeedback', () => ({
  reportKittyDiagramEditFailure: reportFailMock,
}))

vi.mock('@/composables/kitty/kittyWorkflowTrace', () => ({
  traceKittyWorkflow: vi.fn(),
}))

vi.mock('@/composables/kitty/pipeline/editTurn', () => ({
  markKittyServerStepOk: vi.fn(),
}))

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    get collabSessionActive() {
      return collabActive.value
    },
    get type() {
      return diagramType.value
    },
  }),
}))

import { registerKittyDiagramMutationBus } from '@/composables/kitty/registerKittyDiagramMutationBus'

describe('registerKittyDiagramMutationBus collab gate', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    emitMock.mockClear()
    applyVerifiedMock.mockClear()
    reportFailMock.mockClear()
    onHandlers.clear()
    collabActive.value = true
    diagramType.value = 'mindmap'
    registerKittyDiagramMutationBus()
  })

  it('nacks verified mutation with collab_active and does not apply', async () => {
    const sendAck = vi.fn()
    const handler = onHandlers.get('kitty:diagram_mutation_requested')
    expect(handler).toBeTypeOf('function')

    await Promise.resolve(
      handler?.({
        action: 'add_node',
        updates: { text: 'A' },
        mutationId: 'mut-collab-1',
        sendAck,
        lane: 'desktop',
        hubPersist: {
          buildContext: () => ({}),
          updateContext: () => undefined,
          scope: 'lib-1',
        },
      })
    )

    expect(applyVerifiedMock).not.toHaveBeenCalled()
    expect(sendAck).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'diagram_mutation_ack',
        mutation_id: 'mut-collab-1',
        verified: false,
        error_code: 'collab_active',
      })
    )
    expect(reportFailMock).toHaveBeenCalledWith(
      expect.objectContaining({ errorCode: 'collab_active' })
    )
  })

  it('applies when collab is inactive', async () => {
    collabActive.value = false
    applyVerifiedMock.mockResolvedValue({
      verified: true,
      hubPersistOk: true,
      verificationError: undefined,
    })
    const sendAck = vi.fn()
    const handler = onHandlers.get('kitty:diagram_mutation_requested')

    await Promise.resolve(
      handler?.({
        action: 'add_node',
        updates: { text: 'A' },
        mutationId: 'mut-ok-1',
        sendAck,
        lane: 'desktop',
      })
    )

    expect(applyVerifiedMock).toHaveBeenCalled()
    expect(reportFailMock).not.toHaveBeenCalled()
  })

  it('does not fall back debug summary into chat userSummary', async () => {
    collabActive.value = false
    applyVerifiedMock.mockResolvedValue({
      verified: true,
      hubPersistOk: true,
      verificationError: undefined,
    })
    const sendAck = vi.fn()
    const handler = onHandlers.get('kitty:diagram_mutation_requested')

    await Promise.resolve(
      handler?.({
        action: 'add_node',
        updates: { text: 'A' },
        mutationId: 'mut-quiet-1',
        sendAck,
        lane: 'desktop',
        // Multi-step chain omits userSummary so coalesced acks own chat.
      })
    )

    const executed = emitMock.mock.calls.find(
      (call) => call[0] === 'voice:diagram_update_executed'
    )
    expect(executed?.[1]).toMatchObject({
      action: 'add_node',
      verified: true,
      userSummary: undefined,
    })
  })
})
