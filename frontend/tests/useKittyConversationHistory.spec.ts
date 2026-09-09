import { computed, nextTick, ref } from 'vue'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useKittyConversationHistory } from '@/composables/kitty/conversation/useKittyConversationHistory'

const { fetchOneSentenceTurnsMock } = vi.hoisted(() => ({
  fetchOneSentenceTurnsMock: vi.fn(async () => []),
}))

vi.mock('@/composables/canvasToolbar/useOneSentenceSessionTurns', () => ({
  fetchOneSentenceTurns: fetchOneSentenceTurnsMock,
  appendOneSentenceTurn: vi.fn(async () => true),
  migrateOneSentenceScope: vi.fn(async () => true),
}))

vi.mock('@/composables/canvasToolbar/oneSentenceChatLines', () => ({
  pickOneSentenceWelcome: () => 'Hi — tell me what diagram to create.',
  pickOneSentenceGenerateDone: () => 'Diagram ready.',
}))

vi.mock('@/composables/core/useLanguage', () => ({
  useLanguage: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
    currentLanguage: { value: 'zh' },
  }),
}))

describe('useKittyConversationHistory', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    fetchOneSentenceTurnsMock.mockReset()
    fetchOneSentenceTurnsMock.mockResolvedValue([])
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('refreshHistory keeps the live thread when fetch returns empty', async () => {
    const history = useKittyConversationHistory({
      diagramScope: computed(() => 'scope-1'),
      phase: computed(() => 'edit'),
    })
    history.replyState.showFinalReply(
      '想怎么改这张图？\n1) 改主题\n2) 添加分支',
      [
        { index: 1, label: '改主题' },
        { index: 2, label: '添加分支' },
      ],
      'req-1'
    )
    expect(history.messages.value.at(-1)?.choices).toHaveLength(2)

    fetchOneSentenceTurnsMock.mockResolvedValue([])
    await history.refreshHistory()
    await nextTick()

    expect(history.messages.value.at(-1)?.choices).toEqual([
      { index: 1, label: '改主题' },
      { index: 2, label: '添加分支' },
    ])
  })

  it('refreshHistory carries chips onto a persisted ack with the same requestId', async () => {
    const history = useKittyConversationHistory({
      diagramScope: computed(() => 'scope-1'),
      phase: ref('edit'),
    })
    history.replyState.showFinalReply('想怎么改这张图？', [
      { index: 1, label: '改主题' },
      { index: 2, label: '添加分支' },
    ], 'req-1')

    fetchOneSentenceTurnsMock.mockResolvedValue([
      {
        turn_id: 't1',
        ts: 1,
        role: 'kitty',
        content: '想怎么改这张图？\n1) 改主题\n2) 添加分支\n请回复序号或选项内容。',
        phase: 'edit',
        source: 'ack',
        request_id: 'req-1',
      },
    ])
    await history.refreshHistory()

    expect(history.messages.value).toHaveLength(1)
    expect(history.messages.value[0]?.choices).toEqual([
      { index: 1, label: '改主题' },
      { index: 2, label: '添加分支' },
    ])
  })
})
