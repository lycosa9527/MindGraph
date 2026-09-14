/**
 * Kitty job status → chat bubble.
 *
 * Face / voice phases are connection UX. The chat bubble follows the open job:
 * thinking/working stay on one thinking bubble; only a completed job becomes
 * a response bubble.
 */
import type { KittyAgentState } from '@/composables/kitty/kittyAgentTypes'

export type KittyChatJob = 'idle' | 'thinking' | 'working' | 'done'

export type KittyChatBubbleKind = 'thinking' | 'response'

export type KittyReplyKind = 'progress' | 'final' | 'conversational'

export const KITTY_FILL_DONE_ACTIONS = new Set(['auto_complete', 'auto_complete_branch'])

export const KITTY_FACE_STATES: readonly KittyAgentState[] = [
  'idle',
  'connecting',
  'active',
  'listening',
  'speaking',
  'thinking',
  'error',
]

export const KITTY_VOICE_PHASES = ['listening', 'speaking', 'active', 'thinking'] as const

export type KittyJobStatusInput = {
  replyKind?: KittyReplyKind
  action?: string
  hasThinkingBubble: boolean
  canvasGenerating: boolean
  agentState?: KittyAgentState
}

export type KittyJobStatus = {
  job: KittyChatJob
  bubble: KittyChatBubbleKind | null
  promoteToResponse: boolean
}

export function isKittyFillDoneAction(action?: string): boolean {
  return Boolean(action && KITTY_FILL_DONE_ACTIONS.has(action))
}

export function shouldPromoteKittyReplyToResponse(input: {
  replyKind?: KittyReplyKind
  action?: string
  canvasGenerating: boolean
}): boolean {
  if (input.replyKind !== 'final' && input.replyKind !== 'conversational') {
    return false
  }
  if (!input.canvasGenerating) {
    return true
  }
  return isKittyFillDoneAction(input.action)
}

export function resolveKittyJobStatus(input: KittyJobStatusInput): KittyJobStatus {
  const promoteToResponse = shouldPromoteKittyReplyToResponse(input)
  if (promoteToResponse) {
    return { job: 'done', bubble: 'response', promoteToResponse: true }
  }
  if (input.canvasGenerating) {
    return { job: 'working', bubble: 'thinking', promoteToResponse: false }
  }
  if (
    input.replyKind === 'progress' ||
    input.hasThinkingBubble ||
    input.agentState === 'thinking'
  ) {
    return { job: 'thinking', bubble: 'thinking', promoteToResponse: false }
  }
  if (input.agentState === 'speaking') {
    return { job: 'done', bubble: 'response', promoteToResponse: false }
  }
  return { job: 'idle', bubble: null, promoteToResponse: false }
}
