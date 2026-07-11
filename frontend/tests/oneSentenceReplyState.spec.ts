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

    replyState.handleReplyPayload({ text: '分支已添加', kind: 'final' })
    replyState.handleReplyPayload({ text: '正在自动补全…', kind: 'progress' })
    replyState.handleReplyPayload({
      text: '智能生成子图：A、B',
      kind: 'final',
    })

    expect(messages.value.map((row) => row.text)).toEqual([
      '分支已添加',
      '正在自动补全…',
      '智能生成子图：A、B',
    ])
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
})
