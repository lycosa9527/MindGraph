/**
 * Apply edit/delete results to in-memory message lists without refetching.
 */

export interface PatchableChatMessage {
  id: number
  content: string
  is_deleted?: boolean
  edited_at?: string | null
}

export function applyEditedChatMessage<T extends PatchableChatMessage>(
  messages: T[],
  updated: T
): void {
  const idx = messages.findIndex((row) => row.id === updated.id)
  if (idx >= 0) {
    Object.assign(messages[idx], updated)
  }
}

export function applyDeletedChatMessage<T extends PatchableChatMessage>(
  messages: T[],
  messageId: number
): void {
  const row = messages.find((item) => item.id === messageId)
  if (row) {
    row.is_deleted = true
    row.content = ''
  }
}
