/**
 * One-sentence Kitty chat reply state — decoupled from diagram mutations.
 * Thinking/progress is one ephemeral bubble; the final reply replaces it.
 */
import type { Ref } from 'vue'

import { resolveClarifyChoices } from '@/composables/canvasToolbar/oneSentenceClarifyChoices'
import { shouldPromoteKittyReplyToResponse } from '@/composables/kitty/kittyJobStatus'
import type {
  OneSentenceChatMessage,
  OneSentenceClarifyChoice,
} from '@/stores/oneSentence'

export type OneSentenceReplyKind = 'progress' | 'final' | 'conversational'

export type OneSentenceReplyPayload = {
  text: string
  kind: OneSentenceReplyKind
  action?: string
  choices?: OneSentenceClarifyChoice[]
  requestId?: string
}

export type OneSentencePushExtras = {
  choices?: OneSentenceClarifyChoice[]
  requestId?: string
  thinking?: boolean
}

export function createOneSentenceReplyState(options: {
  messages: Ref<OneSentenceChatMessage[]>
  pushKittyMessage: (
    text: string,
    streaming?: boolean,
    extras?: OneSentencePushExtras
  ) => string
  replaceKittyMessage: (messageId: string, text: string, streaming?: boolean) => void
  scrollChatToBottom: () => void
  isCanvasJobOpen?: () => boolean
}) {
  let lastFinalReplyText = ''
  let streamingMessageId: string | null = null
  let thinkingMessageId: string | null = null
  let pendingFinal: {
    text: string
    choices?: OneSentenceClarifyChoice[]
    requestId?: string
  } | null = null

  function consumeOpenChoices(): void {
    const rows = options.messages.value
    if (!rows.some((row) => row.choices?.length && !row.choicesConsumed)) {
      return
    }
    options.messages.value = rows.map((row) =>
      row.choices?.length && !row.choicesConsumed
        ? { ...row, choicesConsumed: true }
        : row
    )
  }

  function resolveThinkingMessageId(): string | null {
    if (thinkingMessageId && options.messages.value.some((row) => row.id === thinkingMessageId)) {
      return thinkingMessageId
    }
    const leftover = options.messages.value.find((row) => row.thinking)
    thinkingMessageId = leftover?.id ?? null
    return thinkingMessageId
  }

  function removeThinkingMessage(): void {
    resolveThinkingMessageId()
    const id = thinkingMessageId
    thinkingMessageId = null
    if (!options.messages.value.some((row) => row.thinking || row.id === id)) {
      return
    }
    options.messages.value = options.messages.value.filter(
      (row) => !row.thinking && row.id !== id
    )
  }

  function finalizeConversationalStream(): void {
    const rows = options.messages.value
    if (rows.some((row) => row.streaming && !row.thinking)) {
      options.messages.value = rows.map((row) =>
        row.streaming && !row.thinking ? { ...row, streaming: false } : row
      )
    }
    streamingMessageId = null
  }

  function showFinalReply(
    text: string,
    choices?: OneSentenceClarifyChoice[],
    requestId?: string,
    action?: string
  ): boolean {
    const trimmed = text.trim()
    if (trimmed === '') {
      return false
    }
    if (
      !shouldPromoteKittyReplyToResponse({
        replyKind: 'final',
        action,
        canvasGenerating: options.isCanvasJobOpen?.() === true,
      })
    ) {
      pendingFinal = { text: trimmed, choices, requestId }
      return false
    }
    pendingFinal = null
    removeThinkingMessage()
    finalizeConversationalStream()
    const resolved = resolveClarifyChoices(choices, trimmed)
    const rid = requestId?.trim() || undefined
    const last = options.messages.value[options.messages.value.length - 1]
    if (last?.role === 'kitty' && last.text === trimmed) {
      lastFinalReplyText = trimmed
      if ((resolved?.length && !last.choices?.length) || (rid && !last.requestId)) {
        const idx = options.messages.value.length - 1
        const next = [...options.messages.value]
        next[idx] = {
          ...last,
          ...(resolved?.length && !last.choices?.length ? { choices: resolved } : {}),
          ...(rid && !last.requestId ? { requestId: rid } : {}),
        }
        options.messages.value = next
      }
      return true
    }
    if (trimmed === lastFinalReplyText && !resolved?.length) {
      return true
    }
    consumeOpenChoices()
    options.pushKittyMessage(trimmed, false, {
      ...(resolved?.length ? { choices: resolved } : {}),
      ...(rid ? { requestId: rid } : {}),
    })
    lastFinalReplyText = trimmed
    return true
  }

  function showProgressReply(text: string): void {
    const trimmed = text.trim()
    if (trimmed === '') {
      return
    }
    finalizeConversationalStream()
    const existingId = resolveThinkingMessageId()
    if (existingId) {
      options.replaceKittyMessage(existingId, trimmed, true)
      return
    }
    thinkingMessageId = options.pushKittyMessage(trimmed, true, { thinking: true })
  }

  function handleReplyPayload(payload: OneSentenceReplyPayload): boolean {
    const trimmed = payload.text.trim()
    if (trimmed === '') {
      return false
    }
    if (payload.kind === 'progress') {
      showProgressReply(trimmed)
      return false
    }
    return showFinalReply(trimmed, payload.choices, payload.requestId, payload.action)
  }

  function resetForNewTurn(): void {
    lastFinalReplyText = ''
    pendingFinal = null
    removeThinkingMessage()
    finalizeConversationalStream()
    consumeOpenChoices()
  }

  function flushWhenCanvasIdle(): void {
    if (options.isCanvasJobOpen?.() === true || pendingFinal == null) {
      return
    }
    if (resolveThinkingMessageId()) {
      pendingFinal = null
      return
    }
    const held = pendingFinal
    pendingFinal = null
    showFinalReply(held.text, held.choices, held.requestId)
  }

  function hasInFlightThinking(): boolean {
    return resolveThinkingMessageId() != null
  }

  return {
    handleReplyPayload,
    showFinalReply,
    showProgressReply,
    finalizeConversationalStream,
    resetForNewTurn,
    consumeOpenChoices,
    hasInFlightThinking,
    flushWhenCanvasIdle,
  }
}
