/**
 * One-sentence Kitty chat reply state — decoupled from diagram mutations.
 * Structural success replies come from verified diagram events; progress from text_chunk.
 */
import type { Ref } from 'vue'

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

export function createOneSentenceReplyState(options: {
  messages: Ref<OneSentenceChatMessage[]>
  pushKittyMessage: (
    text: string,
    streaming?: boolean,
    extras?: { choices?: OneSentenceClarifyChoice[] }
  ) => string
  replaceKittyMessage: (messageId: string, text: string, streaming?: boolean) => void
  scrollChatToBottom: () => void
}) {
  let lastFinalReplyText = ''
  let streamingMessageId: string | null = null
  let progressMessageId: string | null = null

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

  function finalizeConversationalStream(): void {
    if (!streamingMessageId) {
      return
    }
    const idx = options.messages.value.findIndex((m) => m.id === streamingMessageId)
    if (idx >= 0) {
      const next = [...options.messages.value]
      next[idx] = { ...next[idx], streaming: false }
      options.messages.value = next
    }
    streamingMessageId = null
  }

  function clearProgressMessage(): void {
    progressMessageId = null
  }

  function showFinalReply(text: string, choices?: OneSentenceClarifyChoice[]): void {
    const trimmed = text.trim()
    if (trimmed === '') {
      return
    }
    finalizeConversationalStream()
    clearProgressMessage()
    consumeOpenChoices()
    if (trimmed === lastFinalReplyText && !choices?.length) {
      return
    }
    const last = options.messages.value[options.messages.value.length - 1]
    if (last?.role === 'kitty' && last.text === trimmed && !choices?.length) {
      lastFinalReplyText = trimmed
      return
    }
    options.pushKittyMessage(trimmed, false, choices?.length ? { choices } : undefined)
    lastFinalReplyText = trimmed
  }

  function showProgressReply(text: string): void {
    const trimmed = text.trim()
    if (trimmed === '') {
      return
    }
    finalizeConversationalStream()
    if (progressMessageId) {
      options.replaceKittyMessage(progressMessageId, trimmed, false)
      return
    }
    progressMessageId = options.pushKittyMessage(trimmed, false)
  }

  function appendConversationalStream(chunk: string): void {
    const piece = chunk.trim()
    if (piece === '') {
      return
    }
    clearProgressMessage()

    if (!streamingMessageId) {
      streamingMessageId = options.pushKittyMessage(piece, true)
      return
    }

    const idx = options.messages.value.findIndex((m) => m.id === streamingMessageId)
    if (idx < 0) {
      streamingMessageId = options.pushKittyMessage(piece, true)
      return
    }

    const row = options.messages.value[idx]
    const merged = `${row.text}${chunk}`
    const next = [...options.messages.value]
    next[idx] = { ...row, text: merged, streaming: true }
    options.messages.value = next
    options.scrollChatToBottom()
  }

  function handleReplyPayload(payload: OneSentenceReplyPayload): void {
    const trimmed = payload.text.trim()
    if (trimmed === '') {
      return
    }
    if (payload.kind === 'progress') {
      showProgressReply(trimmed)
      return
    }
    if (payload.kind === 'conversational') {
      appendConversationalStream(trimmed)
      return
    }
    showFinalReply(trimmed, payload.choices)
  }

  function resetForNewTurn(): void {
    lastFinalReplyText = ''
    clearProgressMessage()
    finalizeConversationalStream()
    consumeOpenChoices()
  }

  return {
    handleReplyPayload,
    showFinalReply,
    finalizeConversationalStream,
    resetForNewTurn,
    consumeOpenChoices,
  }
}
