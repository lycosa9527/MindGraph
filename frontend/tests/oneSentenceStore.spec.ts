import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useOneSentenceStore } from '@/stores/oneSentence'

describe('useOneSentenceStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('tracks request lifecycle queued → inflight → done', () => {
    const store = useOneSentenceStore()
    const req = store.registerUserRequest('添加中国音乐分支', 'queued')
    expect(store.getRequest(req.requestId)?.status).toBe('queued')
    expect(store.messages.at(-1)?.status).toBe('queued')

    store.markRequestInflight(req.requestId)
    expect(store.getRequest(req.requestId)?.status).toBe('inflight')
    expect(store.activeRequestId).toBe(req.requestId)

    store.applyAckOutcome(req.requestId, 'done')
    expect(store.getRequest(req.requestId)?.status).toBe('done')
    expect(store.activeRequestId).toBeNull()
  })

  it('FIFO busy queue dequeues in order', () => {
    const store = useOneSentenceStore()
    const a = store.registerUserRequest('第一句', 'queued')
    const b = store.registerUserRequest('第二句', 'queued')
    store.enqueueBusyEdit(a.requestId)
    store.enqueueBusyEdit(b.requestId)

    expect(store.dequeueBusyEdit()?.text).toBe('第一句')
    expect(store.dequeueBusyEdit()?.text).toBe('第二句')
    expect(store.dequeueBusyEdit()).toBeNull()
  })

  it('hydrates bubbles and status from durable turns', () => {
    const store = useOneSentenceStore()
    store.hydrateFromTurns([
      {
        turn_id: 'u1',
        role: 'user',
        content: '改成流行音乐',
        request_id: 'req-1',
      },
      {
        turn_id: 'k1',
        role: 'kitty',
        content: '已改好',
        request_id: 'req-1',
        outcome: 'success',
      },
      {
        turn_id: 'u2',
        role: 'user',
        content: '失败的请求',
        request_id: 'req-2',
      },
      {
        turn_id: 'k2',
        role: 'kitty',
        content: '做不到',
        request_id: 'req-2',
        outcome: 'failed',
      },
    ])

    expect(store.messages).toHaveLength(4)
    expect(store.getRequest('req-1')?.status).toBe('done')
    expect(store.getRequest('req-2')?.status).toBe('failed')
    expect(store.messages.find((m) => m.requestId === 'req-1' && m.role === 'user')?.status).toBe(
      'done'
    )
  })

  it('rotates ephemeral scope on canvas reset', () => {
    const store = useOneSentenceStore()
    const before = store.ephemeralScope
    store.registerUserRequest('hello', 'inflight')
    store.onCanvasReset()
    expect(store.ephemeralScope).not.toBe(before)
    expect(store.messages).toHaveLength(0)
    expect(store.phase).toBe('create')
    expect(Object.keys(store.requests)).toHaveLength(0)
  })

  it('resetChatUiForWelcome clears bubbles without rotating ephemeral scope', () => {
    const store = useOneSentenceStore()
    const before = store.ephemeralScope
    store.setLibraryScope('diagram-a')
    store.setPhase('edit')
    store.setDraft('旧草稿')
    store.registerUserRequest('旧对话', 'done')

    store.resetChatUiForWelcome()

    expect(store.ephemeralScope).toBe(before)
    expect(store.libraryScope).toBe('diagram-a')
    expect(store.messages).toHaveLength(0)
    expect(store.phase).toBe('create')
    expect(store.draft).toBe('')
    expect(Object.keys(store.requests)).toHaveLength(0)
  })

  it('canvas reset unbinds library scope so a new diagram gets a fresh thread', () => {
    const store = useOneSentenceStore()
    store.setLibraryScope('diagram-a')
    store.setPhase('edit')
    store.registerUserRequest('diagram A chat', 'done')

    store.onCanvasReset()

    expect(store.libraryScope).toBeNull()
    expect(store.messages).toHaveLength(0)
    expect(store.phase).toBe('create')
    expect(store.diagramScope).toBe(store.ephemeralScope)
  })
})
