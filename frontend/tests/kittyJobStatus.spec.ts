import { ref } from 'vue'

import { describe, expect, it } from 'vitest'

import { createOneSentenceReplyState } from '@/composables/canvasToolbar/oneSentenceReplyState'
import {
  KITTY_FACE_STATES,
  KITTY_VOICE_PHASES,
  resolveKittyJobStatus,
  shouldPromoteKittyReplyToResponse,
} from '@/composables/kitty/kittyJobStatus'

function makeReplyState(canvasOpen: { value: boolean }) {
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
        { id, role: 'kitty', text, streaming, thinking: extras?.thinking },
      ]
      return id
    },
    replaceKittyMessage: (messageId, text, streaming = false) => {
      messages.value = messages.value.map((row) =>
        row.id === messageId ? { ...row, text, streaming } : row
      )
    },
    scrollChatToBottom: () => undefined,
    isCanvasJobOpen: () => canvasOpen.value,
  })
  return { messages, replyState }
}

describe('Kitty job status vs chat bubble', () => {
  it('documents face states and voice phases — no separate waiting-for-llm face', () => {
    expect(KITTY_FACE_STATES).toEqual([
      'idle',
      'connecting',
      'active',
      'listening',
      'speaking',
      'thinking',
      'error',
    ])
    expect(KITTY_VOICE_PHASES).toEqual(['listening', 'speaking', 'active', 'thinking'])
  })

  it('maps thinking / working / done onto one thinking bubble until the job finishes', () => {
    expect(
      resolveKittyJobStatus({
        replyKind: 'progress',
        hasThinkingBubble: true,
        canvasGenerating: false,
        agentState: 'thinking',
      })
    ).toEqual({ job: 'thinking', bubble: 'thinking', promoteToResponse: false })

    expect(
      resolveKittyJobStatus({
        replyKind: 'progress',
        action: 'auto_complete',
        hasThinkingBubble: true,
        canvasGenerating: true,
        agentState: 'thinking',
      })
    ).toEqual({ job: 'working', bubble: 'thinking', promoteToResponse: false })

    expect(
      resolveKittyJobStatus({
        replyKind: 'final',
        action: 'update_center',
        hasThinkingBubble: true,
        canvasGenerating: true,
      })
    ).toEqual({ job: 'working', bubble: 'thinking', promoteToResponse: false })

    expect(
      resolveKittyJobStatus({
        replyKind: 'final',
        action: 'auto_complete',
        hasThinkingBubble: true,
        canvasGenerating: true,
      })
    ).toEqual({ job: 'done', bubble: 'response', promoteToResponse: true })
  })

  it('does not promote a stray topic-done line while canvas generate is still open', () => {
    expect(
      shouldPromoteKittyReplyToResponse({
        replyKind: 'final',
        action: 'update_center',
        canvasGenerating: true,
      })
    ).toBe(false)
    expect(
      shouldPromoteKittyReplyToResponse({
        replyKind: 'final',
        action: 'auto_complete',
        canvasGenerating: true,
      })
    ).toBe(true)
  })

  it('live stacked fill: thinking stays until generate-done, then becomes the response', () => {
    const canvasOpen = { value: false }
    const { messages, replyState } = makeReplyState(canvasOpen)

    replyState.showProgressReply('正在思考')
    expect(resolveKittyJobStatus({
      replyKind: 'progress',
      hasThinkingBubble: messages.value.some((row) => row.thinking),
      canvasGenerating: canvasOpen.value,
      agentState: 'thinking',
    }).bubble).toBe('thinking')

    replyState.showProgressReply('主题换成「中国高等教育」了。')
    canvasOpen.value = true
    replyState.showProgressReply('跟着你，全图自动补全…')
    replyState.handleReplyPayload({
      text: '主题换成「中国高等教育」了。',
      kind: 'final',
      action: 'update_center',
    })

    expect(messages.value).toHaveLength(1)
    expect(messages.value[0]?.thinking).toBe(true)
    expect(messages.value[0]?.text).toBe('跟着你，全图自动补全…')

    replyState.handleReplyPayload({
      text: '整张导图补全好了。',
      kind: 'final',
      action: 'auto_complete',
    })
    expect(messages.value.map((row) => row.text)).toEqual(['整张导图补全好了。'])
    expect(messages.value.some((row) => row.thinking)).toBe(false)
  })

  it('drops a held topic-done when generate ends so fill-done still owns the bubble', () => {
    const canvasOpen = { value: true }
    const { messages, replyState } = makeReplyState(canvasOpen)

    replyState.showProgressReply('跟着你，全图自动补全…')
    expect(
      replyState.showFinalReply('主题换成「中国高等教育」了。', undefined, undefined, 'update_center')
    ).toBe(false)
    expect(messages.value[0]?.thinking).toBe(true)

    canvasOpen.value = false
    replyState.flushWhenCanvasIdle()
    expect(messages.value[0]?.thinking).toBe(true)
    expect(messages.value[0]?.text).toBe('跟着你，全图自动补全…')

    replyState.handleReplyPayload({
      text: '整张导图补全好了。',
      kind: 'final',
      action: 'auto_complete',
    })
    expect(messages.value.map((row) => row.text)).toEqual(['整张导图补全好了。'])
  })
})
