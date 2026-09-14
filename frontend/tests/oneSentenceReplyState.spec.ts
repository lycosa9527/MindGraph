import { ref } from 'vue'

import { describe, expect, it } from 'vitest'

import { createOneSentenceReplyState } from '@/composables/canvasToolbar/oneSentenceReplyState'

describe('oneSentenceReplyState', () => {
  it('shows separate final replies instead of merging unrelated chunks', () => {
    const messages = ref<
      Array<{
        id: string
        role: 'kitty' | 'user'
        text: string
        streaming?: boolean
        thinking?: boolean
        choices?: Array<{ index: number; label: string }>
        choicesConsumed?: boolean
      }>
    >([])
    const ids: string[] = []

    const replyState = createOneSentenceReplyState({
      messages,
      pushKittyMessage: (text, streaming = false, extras) => {
        const id = `msg-${ids.length + 1}`
        ids.push(id)
        messages.value = [
          ...messages.value,
          {
            id,
            role: 'kitty',
            text,
            streaming,
            thinking: extras?.thinking,
            choices: extras?.choices,
          },
        ]
        return id
      },
      replaceKittyMessage: (messageId, text, streaming = false) => {
        messages.value = messages.value.map((row) =>
          row.id === messageId ? { ...row, text, streaming } : row
        )
      },
      scrollChatToBottom: () => undefined,
    })

    replyState.handleReplyPayload({ text: '分支已添加', kind: 'final' })
    replyState.handleReplyPayload({ text: '正在自动补全…', kind: 'progress' })
    expect(messages.value.map((row) => row.text)).toEqual(['分支已添加', '正在自动补全…'])
    expect(messages.value[1]?.thinking).toBe(true)
    replyState.handleReplyPayload({
      text: '智能生成子图：A、B',
      kind: 'final',
    })

    expect(messages.value.map((row) => row.text)).toEqual([
      '分支已添加',
      '智能生成子图：A、B',
    ])
    expect(messages.value.some((row) => row.thinking)).toBe(false)
  })

  it('drops the thinking bubble when the job-done reply arrives', () => {
    const messages = ref<
      Array<{
        id: string
        role: 'kitty' | 'user'
        text: string
        streaming?: boolean
        thinking?: boolean
      }>
    >([])
    const ids: string[] = []

    const replyState = createOneSentenceReplyState({
      messages,
      pushKittyMessage: (text, streaming = false, extras) => {
        const id = `msg-${ids.length + 1}`
        ids.push(id)
        messages.value = [
          ...messages.value,
          {
            id,
            role: 'kitty',
            text,
            streaming,
            thinking: extras?.thinking,
          },
        ]
        return id
      },
      replaceKittyMessage: (messageId, text, streaming = false) => {
        messages.value = messages.value.map((row) =>
          row.id === messageId ? { ...row, text, streaming } : row
        )
      },
      scrollChatToBottom: () => undefined,
    })

    replyState.showProgressReply('正在思考')
    replyState.handleReplyPayload({ text: '好的，正在添加「品牌」…', kind: 'progress' })
    expect(messages.value).toHaveLength(1)
    expect(messages.value[0]?.text).toBe('好的，正在添加「品牌」…')
    replyState.handleReplyPayload({ text: '好，加上「品牌」。', kind: 'final' })
    expect(messages.value.map((row) => row.text)).toEqual(['好，加上「品牌」。'])
  })

  it('dedupes final ack against the same diagram user_summary', () => {
    const messages = ref<
      Array<{
        id: string
        role: 'kitty' | 'user'
        text: string
        streaming?: boolean
        choices?: Array<{ index: number; label: string }>
        choicesConsumed?: boolean
      }>
    >([])
    const ids: string[] = []

    const replyState = createOneSentenceReplyState({
      messages,
      pushKittyMessage: (text, streaming = false, extras) => {
        const id = `msg-${ids.length + 1}`
        ids.push(id)
        messages.value = [
          ...messages.value,
          {
            id,
            role: 'kitty',
            text,
            streaming,
            choices: extras?.choices,
          },
        ]
        return id
      },
      replaceKittyMessage: (messageId, text, streaming = false) => {
        messages.value = messages.value.map((row) =>
          row.id === messageId ? { ...row, text, streaming } : row
        )
      },
      scrollChatToBottom: () => undefined,
    })

    replyState.showFinalReply('「品牌」分支已添加，正在自动补全…')
    replyState.handleReplyPayload({
      text: '「品牌」分支已添加，正在自动补全…',
      kind: 'final',
    })

    expect(messages.value.map((row) => row.text)).toEqual([
      '「品牌」分支已添加，正在自动补全…',
    ])
  })

  it('attaches clarify choices and consumes them on the next turn', () => {
    const messages = ref<
      Array<{
        id: string
        role: 'kitty' | 'user'
        text: string
        streaming?: boolean
        choices?: Array<{ index: number; label: string }>
        choicesConsumed?: boolean
      }>
    >([])
    const ids: string[] = []

    const replyState = createOneSentenceReplyState({
      messages,
      pushKittyMessage: (text, streaming = false, extras) => {
        const id = `msg-${ids.length + 1}`
        ids.push(id)
        messages.value = [
          ...messages.value,
          {
            id,
            role: 'kitty',
            text,
            streaming,
            choices: extras?.choices,
          },
        ]
        return id
      },
      replaceKittyMessage: (messageId, text, streaming = false) => {
        messages.value = messages.value.map((row) =>
          row.id === messageId ? { ...row, text, streaming } : row
        )
      },
      scrollChatToBottom: () => undefined,
    })

    replyState.handleReplyPayload({
      text: '画布上有两个「地理位置」分支，你想补全哪一个？',
      kind: 'final',
      choices: [
        { index: 1, label: '第一个 地理位置' },
        { index: 2, label: '第二个 地理位置' },
      ],
    })

    expect(messages.value[0]?.choices).toEqual([
      { index: 1, label: '第一个 地理位置' },
      { index: 2, label: '第二个 地理位置' },
    ])
    expect(messages.value[0]?.choicesConsumed).toBeUndefined()

    replyState.resetForNewTurn()
    expect(messages.value[0]?.choicesConsumed).toBe(true)
  })

  it('parses numbered options from reply text and keeps them on a duplicate ack', () => {
    const messages = ref<
      Array<{
        id: string
        role: 'kitty' | 'user'
        text: string
        streaming?: boolean
        choices?: Array<{ index: number; label: string }>
        choicesConsumed?: boolean
      }>
    >([])
    const ids: string[] = []

    const replyState = createOneSentenceReplyState({
      messages,
      pushKittyMessage: (text, streaming = false, extras) => {
        const id = `msg-${ids.length + 1}`
        ids.push(id)
        messages.value = [
          ...messages.value,
          {
            id,
            role: 'kitty',
            text,
            streaming,
            choices: extras?.choices,
          },
        ]
        return id
      },
      replaceKittyMessage: (messageId, text, streaming = false) => {
        messages.value = messages.value.map((row) =>
          row.id === messageId ? { ...row, text, streaming } : row
        )
      },
      scrollChatToBottom: () => undefined,
    })

    replyState.handleReplyPayload({
      text: '想怎么改这张图？\n1) 改主题\n2) 添加分支\n3) 自动补全这张图',
      kind: 'final',
    })

    expect(messages.value[0]?.choices).toEqual([
      { index: 1, label: '改主题' },
      { index: 2, label: '添加分支' },
      { index: 3, label: '自动补全这张图' },
    ])
    expect(messages.value[0]?.choicesConsumed).toBeUndefined()

    replyState.showFinalReply('想怎么改这张图？\n1) 改主题\n2) 添加分支\n3) 自动补全这张图')
    expect(messages.value).toHaveLength(1)
    expect(messages.value[0]?.choicesConsumed).toBeUndefined()
    expect(messages.value[0]?.choices).toHaveLength(3)
  })

  it('reuses a leftover thinking row after hydrate drops the pointer id', () => {
    const messages = ref<
      Array<{
        id: string
        role: 'kitty' | 'user'
        text: string
        streaming?: boolean
        thinking?: boolean
      }>
    >([])
    let seq = 0

    const replyState = createOneSentenceReplyState({
      messages,
      pushKittyMessage: (text, streaming = false, extras) => {
        seq += 1
        const id = `msg-${seq}`
        messages.value = [
          ...messages.value,
          {
            id,
            role: 'kitty',
            text,
            streaming,
            thinking: extras?.thinking,
          },
        ]
        return id
      },
      replaceKittyMessage: (messageId, text, streaming = false) => {
        const idx = messages.value.findIndex((row) => row.id === messageId)
        if (idx < 0) {
          throw new Error(`stale thinking id ${messageId}`)
        }
        messages.value = messages.value.map((row) =>
          row.id === messageId ? { ...row, text, streaming } : row
        )
      },
      scrollChatToBottom: () => undefined,
    })

    replyState.showProgressReply('正在思考')
    const leftover = { ...messages.value[0], id: 'hydrated-thinking' }
    messages.value = [leftover]
    replyState.showProgressReply('正在添加「品牌」…')

    expect(messages.value).toHaveLength(1)
    expect(messages.value[0]?.id).toBe('hydrated-thinking')
    expect(messages.value[0]?.text).toBe('正在添加「品牌」…')
    expect(messages.value[0]?.thinking).toBe(true)

    replyState.showFinalReply('好，加上「品牌」。')
    expect(messages.value.map((row) => row.text)).toEqual(['好，加上「品牌」。'])
  })

  it('keeps stacked topic + fill in one thinking bubble until the job-done line', () => {
    const messages = ref<
      Array<{
        id: string
        role: 'kitty' | 'user'
        text: string
        streaming?: boolean
        thinking?: boolean
      }>
    >([])
    let seq = 0

    const replyState = createOneSentenceReplyState({
      messages,
      pushKittyMessage: (text, streaming = false, extras) => {
        seq += 1
        const id = `msg-${seq}`
        messages.value = [
          ...messages.value,
          {
            id,
            role: 'kitty',
            text,
            streaming,
            thinking: extras?.thinking,
          },
        ]
        return id
      },
      replaceKittyMessage: (messageId, text, streaming = false) => {
        messages.value = messages.value.map((row) =>
          row.id === messageId ? { ...row, text, streaming } : row
        )
      },
      scrollChatToBottom: () => undefined,
    })

    replyState.showProgressReply('主题换成「中国高等教育」了。')
    replyState.showProgressReply('跟着你，全图自动补全…')
    expect(messages.value).toHaveLength(1)
    expect(messages.value[0]?.thinking).toBe(true)
    expect(messages.value[0]?.text).toBe('跟着你，全图自动补全…')
    expect(replyState.hasInFlightThinking()).toBe(true)

    replyState.showFinalReply('整张导图补全好了。')
    expect(messages.value.map((row) => row.text)).toEqual(['整张导图补全好了。'])
    expect(messages.value.some((row) => row.thinking)).toBe(false)
    expect(replyState.hasInFlightThinking()).toBe(false)
  })
})
