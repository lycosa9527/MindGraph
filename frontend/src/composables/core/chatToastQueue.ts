/**
 * Chat Toast Queue
 *
 * Module-level singleton that holds the list of pending in-app message toasts.
 * Both the notification composable (producer) and the ChatMessageToast component
 * (consumer) share this reactive state without going through Pinia.
 *
 * Toast lifecycle:
 * - pushChatToast() adds a toast and schedules auto-dismiss after AUTO_DISMISS_MS
 * - dismissChatToast() removes a specific toast and cancels its timer
 * - Max MAX_TOASTS items are kept; oldest is evicted when the cap is reached
 */
import { ref } from 'vue'

const AUTO_DISMISS_MS = 5_000
const MAX_TOASTS = 5

export interface ChatToastNav {
  /** Set for DM toasts — navigate to this partner's conversation */
  partnerId?: number
  /** Set for channel / topic toasts — navigate to this channel */
  channelId?: number
  /** Set for topic-specific toasts — also open the topic view */
  topicId?: number
}

export interface ChatToastItem {
  id: string
  /** 'dm' → blue accent, 'mention' → amber accent */
  type: 'dm' | 'mention'
  senderName: string
  senderAvatar: string | null
  /** Short context line, e.g. "#Math Channel" or "Direct Message" */
  context: string
  content: string
  nav: ChatToastNav
}

const _toasts = ref<ChatToastItem[]>([])
const _timers = new Map<string, ReturnType<typeof setTimeout>>()

export function pushChatToast(item: Omit<ChatToastItem, 'id'>): void {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`

  if (_toasts.value.length >= MAX_TOASTS) {
    dismissChatToast(_toasts.value[0].id)
  }

  _toasts.value = [..._toasts.value, { ...item, id }]
  _timers.set(
    id,
    setTimeout(() => dismissChatToast(id), AUTO_DISMISS_MS)
  )
}

export function dismissChatToast(id: string): void {
  const timer = _timers.get(id)
  if (timer !== undefined) {
    clearTimeout(timer)
    _timers.delete(id)
  }
  _toasts.value = _toasts.value.filter((t) => t.id !== id)
}

export function useChatToastQueue() {
  return { toasts: _toasts }
}
