/**
 * Mobile Kitty chat: create guard, edit pipeline, ASR → send via runKittyEditTurn.
 */
import { computed, nextTick, ref } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useMobileKittyChat } from '@/composables/mobile/useMobileKittyChat'

const {
  appendOneSentenceTurnMock,
  fetchOneSentenceTurnsMock,
  migrateOneSentenceScopeMock,
  onWithOwnerMock,
  removeAllListenersForOwnerMock,
  runKittyEditTurnMock,
} = vi.hoisted(() => ({
  appendOneSentenceTurnMock: vi.fn(async () => true),
  fetchOneSentenceTurnsMock: vi.fn(async () => []),
  migrateOneSentenceScopeMock: vi.fn(async () => true),
  onWithOwnerMock: vi.fn(),
  removeAllListenersForOwnerMock: vi.fn(),
  runKittyEditTurnMock: vi.fn(async () => ({
    ok: true,
    sent: true,
    ctx: { requestId: 'r1', scope: 'scope-abc', lane: 'mobile' as const },
  })),
}))

vi.mock('@/composables/canvasToolbar/useOneSentenceSessionTurns', () => ({
  fetchOneSentenceTurns: fetchOneSentenceTurnsMock,
  appendOneSentenceTurn: appendOneSentenceTurnMock,
  migrateOneSentenceScope: migrateOneSentenceScopeMock,
}))

vi.mock('@/composables/core/useEventBus', () => ({
  eventBus: {
    onWithOwner: onWithOwnerMock,
    removeAllListenersForOwner: removeAllListenersForOwnerMock,
    emit: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
  },
}))

vi.mock('@/composables/core/useLanguage', () => ({
  useLanguage: () => ({
    t: (key: string, fallback?: string) => {
      if (typeof fallback === 'string' && fallback.length > 0) {
        return fallback
      }
      if (key.includes('kittyContextSyncFailed')) {
        return 'Could not sync the canvas. Please try again in a moment.'
      }
      if (key.includes('kittyUnavailable')) {
        return 'Kitty is unavailable.'
      }
      return key
    },
    currentLanguage: { value: 'en' },
  }),
}))

vi.mock('@/composables/canvasToolbar/oneSentenceChatLines', () => ({
  pickOneSentenceWelcome: () => 'Hi — tell me what diagram to create.',
  pickOneSentenceGenerateDone: () => 'Diagram ready. Keep typing to edit.',
}))

vi.mock('@/composables/kitty/pipeline/editTurn', () => ({
  runKittyEditTurn: runKittyEditTurnMock,
  markKittyServerStepOk: vi.fn(),
  markKittyEditTurnCompleted: vi.fn(),
}))

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    type: 'mindmap',
    data: {
      nodes: [
        { id: 'topic', text: 'Root', type: 'topic' },
        { id: 'n1', text: 'Branch', type: 'node' },
      ],
      connections: [],
    },
  }),
}))

describe('useMobileKittyChat', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    appendOneSentenceTurnMock.mockClear()
    fetchOneSentenceTurnsMock.mockClear()
    migrateOneSentenceScopeMock.mockClear()
    onWithOwnerMock.mockClear()
    removeAllListenersForOwnerMock.mockClear()
    runKittyEditTurnMock.mockClear()
    fetchOneSentenceTurnsMock.mockResolvedValue([])
    runKittyEditTurnMock.mockResolvedValue({
      ok: true,
      sent: true,
      ctx: { requestId: 'r1', scope: 'scope-abc', lane: 'mobile' },
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  function mountChat(phase: 'create' | 'edit' = 'edit') {
    const draft = ref('')
    const listening = ref(false)
    const stopListening = vi.fn(() => {
      listening.value = false
    })
    const sendTextMessage = vi.fn(() => true)
    const updateContext = vi.fn()
    const kitty = {
      sendTextMessage,
      updateContext,
      isConnected: ref(true),
    } as unknown as Parameters<typeof useMobileKittyChat>[0]['kitty']
    const funAsr = {
      listening,
      startListening: vi.fn(async () => ({ ok: true as const, utteranceId: 'utt-1' })),
      stopListening,
      toggleListening: vi.fn(),
    } as unknown as Parameters<typeof useMobileKittyChat>[0]['funAsr']

    const chat = useMobileKittyChat({
      kitty,
      funAsr,
      diagramScope: computed(() => 'scope-abc'),
      ephemeralSessionId: computed(() => 'ephemeral-xyz'),
      phase: computed(() => phase),
      draft,
      ensureConnected: vi.fn(async () => true),
      buildContext: () =>
        ({
          diagram_type: 'mindmap',
          active_panel: 'one_sentence',
          selected_nodes: [],
          diagram_data: {},
          one_sentence_phase: phase,
        }) as ReturnType<Parameters<typeof useMobileKittyChat>[0]['buildContext']>,
    })

    const handlers = new Map<string, (payload: unknown) => void>()
    for (const call of onWithOwnerMock.mock.calls) {
      const [event, handler] = call as [string, (payload: unknown) => void]
      handlers.set(event, handler)
    }

    return { chat, draft, sendTextMessage, stopListening, handlers, funAsr, updateContext }
  }

  it('registers shared reply bus handlers on mount', async () => {
    mountChat()
    await nextTick()
    const events = onWithOwnerMock.mock.calls.map((c) => c[0])
    expect(events).toContain('kitty:one_sentence_reply')
    expect(events).toContain('voice:diagram_update_executed')
    expect(events).toContain('kitty:pipeline_step')
  })

  it('on asr_final only buffers until asr_stopped (release-only submit)', async () => {
    const { chat, draft, handlers } = mountChat()
    await nextTick()
    await Promise.resolve()

    const onFinal = handlers.get('kitty:asr_final')
    expect(onFinal).toBeTypeOf('function')
    onFinal?.({ text: '把中心改成秋天', utteranceId: 'utt-hold-1' })

    expect(draft.value).toBe('把中心改成秋天')
    expect(runKittyEditTurnMock).not.toHaveBeenCalled()

    const onStopped = handlers.get('kitty:asr_stopped')
    expect(onStopped).toBeTypeOf('function')
    onStopped?.({ utteranceId: 'utt-hold-1', text: '把中心改成秋天' })

    await vi.waitFor(() => {
      expect(runKittyEditTurnMock).toHaveBeenCalled()
    })
    expect(chat.messages.value.some((m) => m.role === 'user' && m.text === '把中心改成秋天')).toBe(
      true
    )
  })

  it('create phase blocks edit pipeline and prompts to pick a diagram', async () => {
    const { chat } = mountChat('create')
    await nextTick()
    await Promise.resolve()

    const ok = await chat.sendUserText('生成一张秋天的图')
    expect(ok).toBe(false)
    expect(runKittyEditTurnMock).not.toHaveBeenCalled()
    expect(
      chat.messages.value.some(
        (m) => m.role === 'kitty' && m.text.toLowerCase().includes('diagram')
      )
    ).toBe(true)
  })

  it('edit turn failure blocks send', async () => {
    runKittyEditTurnMock.mockResolvedValue({
      ok: false,
      sent: false,
      ctx: { requestId: 'r2', scope: 'scope-abc', lane: 'mobile' },
    })
    const { chat } = mountChat('edit')
    await nextTick()
    await Promise.resolve()

    const ok = await chat.sendUserText('改成春天')
    expect(ok).toBe(false)
  })

  it('migrates ephemeral session turns onto library scope', async () => {
    const scope = ref('ephemeral-xyz')
    const draft = ref('')
    const listening = ref(false)
    const kitty = {
      sendTextMessage: vi.fn(),
      updateContext: vi.fn(),
      isConnected: ref(true),
    } as unknown as Parameters<typeof useMobileKittyChat>[0]['kitty']
    const funAsr = {
      listening,
      startListening: vi.fn(),
      stopListening: vi.fn(),
      toggleListening: vi.fn(),
    } as unknown as Parameters<typeof useMobileKittyChat>[0]['funAsr']

    useMobileKittyChat({
      kitty,
      funAsr,
      diagramScope: computed(() => scope.value),
      ephemeralSessionId: computed(() => 'ephemeral-xyz'),
      phase: computed(() => 'edit'),
      draft,
      ensureConnected: vi.fn(async () => true),
      buildContext: () =>
        ({
          diagram_type: 'mindmap',
          active_panel: 'one_sentence',
          selected_nodes: [],
          diagram_data: {},
        }) as ReturnType<Parameters<typeof useMobileKittyChat>[0]['buildContext']>,
    })

    await nextTick()
    await Promise.resolve()
    expect(migrateOneSentenceScopeMock).not.toHaveBeenCalled()

    scope.value = 'lib-diagram-1'
    await nextTick()
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
    await vi.waitFor(() => {
      expect(migrateOneSentenceScopeMock).toHaveBeenCalledWith('ephemeral-xyz', 'lib-diagram-1')
    })
    await vi.waitFor(() => {
      expect(fetchOneSentenceTurnsMock).toHaveBeenCalledWith('lib-diagram-1')
    })
  })
})
