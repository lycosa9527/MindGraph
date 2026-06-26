import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'

import {
  cloneMindMateMessages,
  mapDifyMessagesToMindMate,
  sanitizeMessagesForStore,
  shouldApplyDifyHistory,
  threadsContentEqual,
  type MindMateMessage,
} from '@/stores/mindmateActiveThread'
import { useMindMateStore } from '@/stores/mindmate'

describe('mindMateActiveThread helpers', () => {
  it('sanitizeMessagesForStore strips preview_url and isStreaming', () => {
    const input: MindMateMessage[] = [
      {
        id: 'm1',
        role: 'user',
        content: 'hello',
        timestamp: 1,
        isStreaming: true,
        files: [
          {
            id: 'f1',
            name: 'pic.png',
            type: 'image',
            size: 10,
            extension: 'png',
            mime_type: 'image/png',
            preview_url: 'blob:fake',
          },
        ],
      },
    ]

    const sanitized = sanitizeMessagesForStore(input)
    expect(sanitized[0].isStreaming).toBe(false)
    expect(sanitized[0].files?.[0].preview_url).toBeUndefined()
    expect(sanitized[0].files?.[0].name).toBe('pic.png')
  })

  it('cloneMindMateMessages returns a deep copy', () => {
    const input: MindMateMessage[] = [
      { id: 'm1', role: 'assistant', content: 'hi', timestamp: 2 },
    ]
    const cloned = cloneMindMateMessages(input)
    cloned[0].content = 'changed'
    expect(input[0].content).toBe('hi')
  })

  it('getActiveThread returns null when conversation id mismatches', () => {
    setActivePinia(createPinia())
    const store = useMindMateStore()
    store.setActiveThread('conv-a', [
      { id: 'm1', role: 'user', content: 'x', timestamp: 1 },
    ], true)

    expect(store.getActiveThread('conv-b')).toBeNull()
    const snapshot = store.getActiveThread('conv-a')
    expect(snapshot?.messages).toHaveLength(1)
    expect(snapshot?.hasGreeted).toBe(true)
  })

  it('getActiveThread without convId returns stored thread', () => {
    setActivePinia(createPinia())
    const store = useMindMateStore()
    store.setActiveThread('conv-a', [
      { id: 'm1', role: 'user', content: 'x', timestamp: 1 },
    ], true)

    const snapshot = store.getActiveThread()
    expect(snapshot?.conversationId).toBe('conv-a')
    expect(snapshot?.messages).toHaveLength(1)
  })

  it('mapDifyMessagesToMindMate preserves difyMessageId on assistant rows', () => {
    const mapped = mapDifyMessagesToMindMate([
      {
        id: 'dify-1',
        query: 'question',
        answer: 'answer',
        created_at: 100,
        feedback: { rating: 'like' },
      },
    ])

    expect(mapped).toHaveLength(2)
    expect(mapped[0].role).toBe('user')
    expect(mapped[1].role).toBe('assistant')
    expect(mapped[1].difyMessageId).toBe('dify-1')
    expect(mapped[1].feedback).toBe('like')
  })

  it('threadsContentEqual compares role and content only', () => {
    const a: MindMateMessage[] = [
      { id: 'a', role: 'user', content: 'q', timestamp: 1 },
      { id: 'b', role: 'assistant', content: 'a', timestamp: 2, difyMessageId: 'x' },
    ]
    const b: MindMateMessage[] = [
      { id: 'c', role: 'user', content: 'q', timestamp: 9 },
      { id: 'd', role: 'assistant', content: 'a', timestamp: 10 },
    ]
    expect(threadsContentEqual(a, b)).toBe(true)
  })

  it('shouldApplyDifyHistory rejects empty or partial Dify copies', () => {
    const local: MindMateMessage[] = [
      { id: 'u', role: 'user', content: 'make diagram', timestamp: 1 },
      { id: 'a', role: 'assistant', content: 'here is the diagram', timestamp: 2 },
    ]

    expect(shouldApplyDifyHistory(local, [])).toBe(false)
    expect(shouldApplyDifyHistory(local, [{ id: 'u2', role: 'user', content: 'make diagram', timestamp: 3 }])).toBe(
      false
    )
    expect(
      shouldApplyDifyHistory(local, [
        { id: 'u3', role: 'user', content: 'make diagram', timestamp: 4 },
        { id: 'a3', role: 'assistant', content: 'updated answer', timestamp: 5 },
      ])
    ).toBe(true)
    expect(shouldApplyDifyHistory(local, [...local])).toBe(false)
  })
})

describe('useMindMateStore active thread lifecycle', () => {
  it('clears active thread on startNewConversation, delete current, and reset', () => {
    setActivePinia(createPinia())
    const store = useMindMateStore()

    store.setCurrentConversation('conv-1')
    store.setActiveThread('conv-1', [
      { id: 'm1', role: 'user', content: 'hi', timestamp: 1 },
    ], true)

    store.startNewConversation()
    expect(store.activeThreadMessages).toHaveLength(0)
    expect(store.activeThreadConversationId).toBeNull()

    store.setCurrentConversation('conv-2')
    store.setActiveThread('conv-2', [
      { id: 'm2', role: 'user', content: 'yo', timestamp: 2 },
    ], true)

    void store.deleteConversation('conv-2')
    expect(store.activeThreadMessages).toHaveLength(0)

    store.setActiveThread('conv-3', [
      { id: 'm3', role: 'user', content: 'again', timestamp: 3 },
    ], false)
    store.reset()
    expect(store.activeThreadMessages).toHaveLength(0)
    expect(store.activeThreadConversationId).toBeNull()
    expect(store.activeThreadHasGreeted).toBe(false)
  })

  it('restore path works when only activeThreadConversationId is set', () => {
    setActivePinia(createPinia())
    const store = useMindMateStore()
    store.setActiveThread('conv-only-thread', [
      { id: 'm1', role: 'assistant', content: 'diagram ready', timestamp: 1 },
    ], true)

    expect(store.currentConversationId).toBeNull()
    const snapshot = store.getActiveThread()
    expect(snapshot?.conversationId).toBe('conv-only-thread')
    expect(snapshot?.messages[0].content).toBe('diagram ready')
  })
})
