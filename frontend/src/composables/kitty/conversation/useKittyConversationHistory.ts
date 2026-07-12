/**
 * Kitty conversation history — shared messages + REST turns for desktop and mobile.
 */
import { type Ref, ref } from 'vue'

import {
  pickOneSentenceGenerateDone,
  pickOneSentenceWelcome,
} from '@/composables/canvasToolbar/oneSentenceChatLines'
import {
  type OneSentenceReplyPayload,
  createOneSentenceReplyState,
} from '@/composables/canvasToolbar/oneSentenceReplyState'
import {
  appendOneSentenceTurn,
  fetchOneSentenceTurns,
  migrateOneSentenceScope,
} from '@/composables/canvasToolbar/useOneSentenceSessionTurns'
import { useLanguage } from '@/composables/core/useLanguage'
import { failKittyTurn, recordPipelineEvent } from '@/composables/kitty/pipeline/trace'
import type { KittyTurnContext } from '@/composables/kitty/pipeline/types'
import type {
  OneSentenceChatMessage,
  OneSentencePhase,
} from '@/stores/oneSentence'
import { nextTick } from 'vue'

export function useKittyConversationHistory(options: {
  diagramScope: Ref<string> | { value: string }
  phase: Ref<OneSentencePhase> | { value: OneSentencePhase }
  /** When provided, use external messages (desktop oneSentence store). */
  messages?: Ref<OneSentenceChatMessage[]>
}): {
  messages: Ref<OneSentenceChatMessage[]>
  sessionHydrated: Ref<boolean>
  chatScrollEl: Ref<HTMLElement | null>
  bootstrapHistory: () => Promise<void>
  appendUserTurn: (
    text: string,
    requestId: string,
    extras?: { ctx?: KittyTurnContext; diagramType?: string; outcome?: string }
  ) => Promise<boolean>
  appendKittyTurn: (
    text: string,
    requestId?: string,
    extras?: { ctx?: KittyTurnContext; outcome?: string }
  ) => Promise<void>
  migrateScope: (fromScope: string, toScope: string) => Promise<boolean>
  seedOpeningLine: () => void
  bindChatScroll: (el: HTMLElement | null) => void
  replyState: ReturnType<typeof createOneSentenceReplyState>
  markActiveRequest: (status: 'done' | 'failed', requestId?: string | null) => void
  activeRequestId: Ref<string | null>
  pushUserMessage: (text: string, requestId: string) => string
  findByRequestId: (requestId: string) => OneSentenceChatMessage | undefined
} {
  const { t: _t, currentLanguage } = useLanguage()
  void _t
  const localMessages = ref<OneSentenceChatMessage[]>([])
  const messages = options.messages ?? localMessages
  const sessionHydrated = ref(false)
  const chatScrollEl = ref<HTMLElement | null>(null)
  const activeRequestId = ref<string | null>(null)
  let bootstrapGeneration = 0
  let messageSeq = 0

  function nextMessageId(): string {
    messageSeq += 1
    return `kitty-hist-msg-${messageSeq}`
  }

  function scrollChatToBottom(): void {
    void nextTick(() => {
      const el = chatScrollEl.value
      if (el) {
        el.scrollTop = el.scrollHeight
      }
    })
  }

  function pushKittyMessage(
    text: string,
    streaming = false,
    extras?: { choices?: OneSentenceChatMessage['choices'] }
  ): string {
    const id = nextMessageId()
    const row: OneSentenceChatMessage = {
      id,
      role: 'kitty',
      text,
      streaming,
    }
    if (extras?.choices?.length) {
      row.choices = extras.choices
    }
    messages.value = [...messages.value, row]
    scrollChatToBottom()
    return id
  }

  function replaceKittyMessage(messageId: string, text: string, streaming = false): void {
    const idx = messages.value.findIndex((m) => m.id === messageId)
    if (idx < 0) {
      pushKittyMessage(text, streaming)
      return
    }
    const next = [...messages.value]
    next[idx] = { ...next[idx], text, streaming }
    messages.value = next
    scrollChatToBottom()
  }

  const replyState = createOneSentenceReplyState({
    messages,
    pushKittyMessage,
    replaceKittyMessage,
    scrollChatToBottom,
  })

  function pushUserMessage(text: string, requestId: string): string {
    const id = nextMessageId()
    messages.value = [
      ...messages.value,
      {
        id,
        role: 'user',
        text,
        requestId,
        status: 'inflight',
      },
    ]
    scrollChatToBottom()
    return id
  }

  function markActiveRequest(status: 'done' | 'failed', requestId?: string | null): void {
    const id = requestId ?? activeRequestId.value
    if (!id) {
      return
    }
    const idx = messages.value.findIndex((m) => m.requestId === id && m.role === 'user')
    if (idx >= 0) {
      const next = [...messages.value]
      next[idx] = { ...next[idx], status }
      messages.value = next
    }
    if (!requestId || activeRequestId.value === id) {
      activeRequestId.value = null
    }
  }

  function seedOpeningLine(): void {
    const seed =
      options.phase.value === 'edit'
        ? pickOneSentenceGenerateDone(currentLanguage.value)
        : pickOneSentenceWelcome(currentLanguage.value)
    if (seed.trim()) {
      pushKittyMessage(seed)
    }
  }

  function hydrateFromTurns(
    turns: Array<{
      turn_id: string
      role: 'user' | 'kitty' | 'meta'
      content: string
      request_id?: string
      outcome?: string
    }>
  ): void {
    const rows: OneSentenceChatMessage[] = []
    for (const turn of turns) {
      if (turn.role !== 'user' && turn.role !== 'kitty') {
        continue
      }
      const content = turn.content?.trim()
      if (!content) {
        continue
      }
      const requestId = turn.request_id?.trim() || undefined
      let status: OneSentenceChatMessage['status']
      if (turn.role === 'user' && requestId) {
        const outcome = (turn.outcome || '').toLowerCase()
        if (outcome === 'failed' || outcome === 'error') {
          status = 'failed'
        } else if (outcome === 'queued') {
          status = 'queued'
        } else {
          status = 'done'
        }
      }
      rows.push({
        id: turn.turn_id || nextMessageId(),
        role: turn.role,
        text: content,
        requestId,
        status,
      })
    }
    messages.value = rows
    scrollChatToBottom()
  }

  async function bootstrapHistory(): Promise<void> {
    const gen = ++bootstrapGeneration
    const scope = options.diagramScope.value
    sessionHydrated.value = false
    if (!scope) {
      messages.value = []
      seedOpeningLine()
      sessionHydrated.value = true
      return
    }
    const restored = await fetchOneSentenceTurns(scope)
    if (gen !== bootstrapGeneration) {
      return
    }
    if (restored.length > 0) {
      hydrateFromTurns(restored)
    } else {
      messages.value = []
      seedOpeningLine()
    }
    sessionHydrated.value = true
  }

  async function appendUserTurn(
    text: string,
    requestId: string,
    extras?: { ctx?: KittyTurnContext; diagramType?: string; outcome?: string }
  ): Promise<boolean> {
    const scope = options.diagramScope.value
    const ctx =
      extras?.ctx ??
      ({
        requestId,
        scope: scope || 'scope',
        lane: 'mobile' as const,
      } satisfies KittyTurnContext)
    if (!scope) {
      failKittyTurn({
        ctx,
        module: 'history',
        step: 'S06_history_user',
        errorCode: 'scope_missing',
      })
      return false
    }
    recordPipelineEvent({
      ctx,
      module: 'history',
      step: 'S06_history_user',
      status: 'started',
    })
    try {
      const ok = await appendOneSentenceTurn(scope, {
        role: 'user',
        content: text,
        phase: options.phase.value,
        source: 'mobile_ui',
        diagram_type: extras?.diagramType,
        request_id: requestId,
        outcome: extras?.outcome,
      })
      if (!ok) {
        failKittyTurn({
          ctx,
          module: 'history',
          step: 'S06_history_user',
          errorCode: 'history_append_failed',
        })
        return false
      }
      recordPipelineEvent({
        ctx,
        module: 'history',
        step: 'S06_history_user',
        status: 'ok',
        detail: text.slice(0, 60),
      })
      return true
    } catch {
      failKittyTurn({
        ctx,
        module: 'history',
        step: 'S06_history_user',
        errorCode: 'history_append_failed',
      })
      return false
    }
  }

  async function appendKittyTurn(
    text: string,
    requestId?: string,
    extras?: { ctx?: KittyTurnContext; outcome?: string }
  ): Promise<void> {
    const scope = options.diagramScope.value
    if (!scope || !text.trim()) {
      return
    }
    const ctx =
      extras?.ctx ??
      ({
        requestId: requestId ?? safeHistRequestId(),
        scope,
        lane: 'mobile' as const,
      } satisfies KittyTurnContext)
    recordPipelineEvent({
      ctx,
      module: 'history',
      step: 'S14_history_reply',
      status: 'started',
    })
    await appendOneSentenceTurn(scope, {
      role: 'kitty',
      content: text,
      phase: options.phase.value,
      source: 'mobile_ui',
      request_id: requestId,
      outcome: extras?.outcome,
    })
    recordPipelineEvent({
      ctx,
      module: 'history',
      step: 'S14_history_reply',
      status: 'ok',
      detail: text.slice(0, 60),
    })
  }

  async function migrateScope(fromScope: string, toScope: string): Promise<boolean> {
    return migrateOneSentenceScope(fromScope, toScope)
  }

  function bindChatScroll(el: HTMLElement | null): void {
    chatScrollEl.value = el
  }

  function findByRequestId(requestId: string): OneSentenceChatMessage | undefined {
    return messages.value.find((m) => m.requestId === requestId)
  }

  return {
    messages,
    sessionHydrated,
    chatScrollEl,
    bootstrapHistory,
    appendUserTurn,
    appendKittyTurn,
    migrateScope,
    seedOpeningLine,
    bindChatScroll,
    replyState,
    markActiveRequest,
    activeRequestId,
    pushUserMessage,
    findByRequestId,
  }
}

function safeHistRequestId(): string {
  return `hist-${Date.now()}`
}
