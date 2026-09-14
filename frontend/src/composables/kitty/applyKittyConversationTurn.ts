/**
 * Merge one persisted peer turn into the local one-sentence thread.
 */
import {
  applyClarifyChoicesOnHydrate,
  choicesFromCommandDetail,
} from '@/composables/canvasToolbar/oneSentenceClarifyChoices'
import type { OneSentenceChatMessage } from '@/stores/oneSentence'

export type KittyConversationTurnPayload = {
  turn_id?: string
  role?: string
  content?: string
  request_id?: string
  outcome?: string
  command_detail?: Record<string, unknown>
}

function turnMessageId(turn: KittyConversationTurnPayload, fallback: string): string {
  const id = turn.turn_id?.trim()
  return id || fallback
}

export function conversationTurnToMessage(
  turn: KittyConversationTurnPayload,
  fallbackId: string
): OneSentenceChatMessage | null {
  if (turn.role !== 'user' && turn.role !== 'kitty') {
    return null
  }
  const content = turn.content?.trim()
  if (!content) {
    return null
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
  const detailChoices =
    turn.role === 'kitty' ? choicesFromCommandDetail(turn.command_detail) : []
  return {
    id: turnMessageId(turn, fallbackId),
    role: turn.role,
    text: content,
    requestId,
    status,
    ...(detailChoices.length >= 2 ? { choices: detailChoices } : {}),
  }
}

export function mergeKittyConversationTurn(
  messages: OneSentenceChatMessage[],
  turn: KittyConversationTurnPayload,
  fallbackId: string
): OneSentenceChatMessage[] | null {
  const row = conversationTurnToMessage(turn, fallbackId)
  if (row == null) {
    return null
  }
  const turnId = row.id
  if (messages.some((item) => item.id === turnId)) {
    return null
  }
  const requestId = row.requestId
  if (
    requestId &&
    messages.some(
      (item) => item.requestId === requestId && item.role === row.role && item.text === row.text
    )
  ) {
    return null
  }
  const lastUser = [...messages].reverse().find((item) => item.role === 'user')
  const dropThinking =
    row.role === 'kitty' &&
    Boolean(row.requestId) &&
    Boolean(lastUser?.requestId) &&
    lastUser?.requestId === row.requestId
  const base = dropThinking ? messages.filter((item) => !item.thinking) : messages
  return applyClarifyChoicesOnHydrate([...base, row], base)
}
