import { createApp, h } from 'vue'

import { createPinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import I18nText from '@/components/common/I18nText.vue'
import MindmateCollabStartPicker from '@/components/mindmate/MindmateCollabStartPicker.vue'
import type { CollabSeedDraft } from '@/utils/mindmateCollabSeed'

const authFetch = vi.hoisted(() => vi.fn())

vi.mock('@/utils/api', () => ({
  authFetch,
}))

vi.mock('@/composables/queries', async () => {
  const { ref } = await import('vue')
  return {
    useConversations: () => ({
      data: ref([
        {
          id: 'conv-old',
          name: '旧对话',
          created_at: 1,
          updated_at: 1,
        },
        {
          id: 'conv-1',
          name: '平行四边形',
          created_at: 2,
          updated_at: 20,
        },
      ]),
      isLoading: ref(false),
      isError: ref(false),
    }),
  }
})

describe('MindmateCollabStartPicker', () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockImplementation(() => ({
      matches: false,
      media: '',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
    authFetch.mockReset()
    authFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        data: [{ query: '这节课怎么设计？', answer: '先抛一个认知冲突。' }],
      }),
    })
  })

  it('lists library conversations and starts a public seminar from the newest one', async () => {
    const host = document.createElement('div')
    const started: Array<{
      visibility: string
      title: string
      seedMessages: CollabSeedDraft[]
    }> = []
    const app = createApp({
      render() {
        return h(MindmateCollabStartPicker, {
          starting: false,
          onStart: (payload: {
            visibility: string
            title: string
            seedMessages: CollabSeedDraft[]
          }) => {
            started.push(payload)
          },
        })
      },
    })
    app.use(createPinia())
    app.component('I18nText', I18nText)
    app.mount(host)

    expect(host.textContent).toContain('Start session')
    expect(host.textContent).toContain('School')
    expect(host.textContent).toContain('Public')
    const titles = [...host.querySelectorAll('.sw-session-title')].map((node) =>
      node.textContent?.trim()
    )
    expect(titles[0]).toContain('平行四边形')
    expect(titles[1]).toContain('旧对话')

    const publicSegment = [...host.querySelectorAll('[role="radio"]')].find((node) =>
      node.textContent?.includes('Public')
    )
    publicSegment?.dispatchEvent(new MouseEvent('click', { bubbles: true }))

    const startButton = host.querySelector('.sw-session-join')
    startButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await vi.waitFor(() => {
      expect(started).toHaveLength(1)
    })

    expect(authFetch).toHaveBeenCalledWith('/api/dify/conversations/conv-1/messages?limit=50')
    expect(started[0]).toEqual({
      visibility: 'network',
      title: '平行四边形',
      seedMessages: [
        { role: 'user', content: '这节课怎么设计？' },
        { role: 'assistant', content: '先抛一个认知冲突。' },
      ],
    })
    app.unmount()
  })
})
