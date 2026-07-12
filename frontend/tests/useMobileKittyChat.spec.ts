/**
 * Mobile Kitty chat: create guard, hub pre-sync, ASR → sendTextMessage.
 */
import { computed, nextTick, ref } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const {
  appendOneSentenceTurnMock,
  fetchOneSentenceTurnsMock,
  migrateOneSentenceScopeMock,
  onWithOwnerMock,
  removeAllListenersForOwnerMock,
  persistVerifiedDiagramToHubMock,
  setHubScopeRevisionMock,
} = vi.hoisted(() => ({
  appendOneSentenceTurnMock: vi.fn(async () => true),
  fetchOneSentenceTurnsMock: vi.fn(async () => []),
  migrateOneSentenceScopeMock: vi.fn(async () => true),
  onWithOwnerMock: vi.fn(),
  removeAllListenersForOwnerMock: vi.fn(),
  persistVerifiedDiagramToHubMock: vi.fn(async () => ({ ok: true, revision: 3 })),
  setHubScopeRevisionMock: vi.fn(),
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
  },
}))

vi.mock('@/composables/kitty/diagramEditHubPersist', () => ({
  persistVerifiedDiagramToHub: persistVerifiedDiagramToHubMock,
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

vi.mock('@/stores/kittySession', () => ({
  useKittySessionStore: () => ({
    hubScopeRevision: 1,
    setHubScopeRevision: setHubScopeRevisionMock,
  }),
}))

import { useMobileKittyChat } from '@/composables/mobile/useMobileKittyChat'

describe('useMobileKittyChat', () => {
  beforeEach(() => {
    appendOneSentenceTurnMock.mockClear()
    fetchOneSentenceTurnsMock.mockClear()
    migrateOneSentenceScopeMock.mockClear()
    onWithOwnerMock.mockClear()
    removeAllListenersForOwnerMock.mockClear()
    persistVerifiedDiagramToHubMock.mockClear()
    setHubScopeRevisionMock.mockClear()
    fetchOneSentenceTurnsMock.mockResolvedValue([])
    persistVerifiedDiagramToHubMock.mockResolvedValue({ ok: true, revision: 3 })
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
    const sendTextMessage = vi.fn()
    const updateContext = vi.fn()
    const kitty = {
      sendTextMessage,
      updateContext,
      isConnected: ref(true),
    } as unknown as Parameters<typeof useMobileKittyChat>[0]['kitty']
    const funAsr = {
      listening,
      startListening: vi.fn(async () => {
        listening.value = true
      }),
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

  it('registers ASR and reply bus handlers on mount', async () => {
    mountChat()
    await nextTick()
    const events = onWithOwnerMock.mock.calls.map((c) => c[0])
    expect(events).toContain('kitty:asr_partial')
    expect(events).toContain('kitty:asr_final')
    expect(events).toContain('kitty:asr_stopped')
    expect(events).toContain('kitty:one_sentence_reply')
    expect(events).toContain('voice:diagram_update_executed')
    expect(events).toContain('voice:context_mutation_ack')
  })

  it('on asr_stopped flushes draft when asr_final never arrived', async () => {
    const { chat, draft, sendTextMessage, handlers } = mountChat()
    await nextTick()
    await Promise.resolve()
    draft.value = '添加一个广东民族文化的分支，并补完'
    const onStopped = handlers.get('kitty:asr_stopped')
    expect(onStopped).toBeTypeOf('function')
    onStopped?.({})
    await vi.waitFor(() => {
      expect(sendTextMessage).toHaveBeenCalledWith(
        '添加一个广东民族文化的分支，并补完',
        expect.any(String)
      )
    })
    expect(chat.messages.value.some((m) => m.role === 'user')).toBe(true)
  })

  it('on asr_final stops mic and sends text with user bubble', async () => {
    const { chat, draft, sendTextMessage, stopListening, handlers } = mountChat()
    await nextTick()
    await Promise.resolve()

    const onFinal = handlers.get('kitty:asr_final')
    expect(onFinal).toBeTypeOf('function')
    onFinal?.({ text: '把中心改成秋天' })

    await vi.waitFor(() => {
      expect(sendTextMessage).toHaveBeenCalledWith('把中心改成秋天', expect.any(String))
    })
    expect(stopListening).toHaveBeenCalled()
    expect(persistVerifiedDiagramToHubMock).toHaveBeenCalled()
    expect(chat.messages.value.some((m) => m.role === 'user' && m.text === '把中心改成秋天')).toBe(
      true
    )
    expect(appendOneSentenceTurnMock).toHaveBeenCalled()
    expect(draft.value).toBe('')
  })

  it('seeds opening line from one-sentence chat pools', async () => {
    const { chat } = mountChat('create')
    await nextTick()
    await Promise.resolve()
    await chat.bootstrapChat()
    expect(
      chat.messages.value.some(
        (m) => m.role === 'kitty' && m.text.includes('tell me what diagram')
      )
    ).toBe(true)
  })

  it('create phase blocks sendTextMessage and prompts to pick a diagram', async () => {
    const { chat, sendTextMessage } = mountChat('create')
    await nextTick()
    await Promise.resolve()

    const ok = await chat.sendUserText('生成一张秋天的图')
    expect(ok).toBe(false)
    expect(sendTextMessage).not.toHaveBeenCalled()
    expect(persistVerifiedDiagramToHubMock).not.toHaveBeenCalled()
    expect(
      chat.messages.value.some(
        (m) => m.role === 'kitty' && m.text.toLowerCase().includes('diagram')
      )
    ).toBe(true)
  })

  it('hub pre-sync failure blocks sendTextMessage', async () => {
    persistVerifiedDiagramToHubMock.mockResolvedValue({ ok: false, error: 'hub_persist_timeout' })
    const { chat, sendTextMessage } = mountChat('edit')
    await nextTick()
    await Promise.resolve()

    const ok = await chat.sendUserText('改成春天')
    expect(ok).toBe(false)
    expect(sendTextMessage).not.toHaveBeenCalled()
    expect(
      chat.messages.value.some((m) => m.role === 'kitty' && m.text.toLowerCase().includes('sync'))
    ).toBe(true)
  })

  it('appends kitty reply from one_sentence_reply final', async () => {
    const { chat, handlers } = mountChat()
    await nextTick()
    const onReply = handlers.get('kitty:one_sentence_reply')
    onReply?.({ text: '已更新中心主题', kind: 'final' })
    await nextTick()
    expect(chat.messages.value.some((m) => m.role === 'kitty' && m.text.includes('已更新'))).toBe(
      true
    )
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

    expect(migrateOneSentenceScopeMock).toHaveBeenCalledWith('ephemeral-xyz', 'lib-diagram-1')
    expect(fetchOneSentenceTurnsMock).toHaveBeenCalledWith('lib-diagram-1')
  })
})
