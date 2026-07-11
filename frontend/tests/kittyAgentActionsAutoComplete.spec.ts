/** Vitest: Kitty agent actions pass topic into auto-complete event. */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const emitMock = vi.fn()

vi.mock('@/composables/core/useEventBus', () => ({
  eventBus: {
    emit: (...args: unknown[]) => emitMock(...args),
  },
}))

vi.mock('@/composables/kitty/kittyWorkflowTrace', () => ({
  traceKittyWorkflow: vi.fn(),
}))

describe('executeKittyAgentAction auto_complete topic', () => {
  beforeEach(() => {
    emitMock.mockClear()
  })

  it('emits diagram:auto_complete_requested with topic from params', async () => {
    const { executeKittyAgentAction } = await import('@/composables/kitty/kittyAgentActions')
    executeKittyAgentAction('auto_complete', { topic: '小学新课标' })
    expect(emitMock).toHaveBeenCalledWith('voice:action_executed', {
      action: 'auto_complete',
      params: { topic: '小学新课标' },
    })
    expect(emitMock).toHaveBeenCalledWith('diagram:auto_complete_requested', {
      source: 'kitty_agent',
      topic: '小学新课标',
    })
  })

  it('omits empty topic', async () => {
    const { executeKittyAgentAction } = await import('@/composables/kitty/kittyAgentActions')
    executeKittyAgentAction('auto_complete', {})
    expect(emitMock).toHaveBeenCalledWith('diagram:auto_complete_requested', {
      source: 'kitty_agent',
      topic: undefined,
    })
  })
})
