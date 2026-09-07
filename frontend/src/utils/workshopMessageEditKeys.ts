/**
 * Keyboard mapping for in-row message edit (Zulip message_edit.ts).
 * Enter saves (same as compose Enter-to-send); Shift+Enter inserts a newline.
 */

export type MessageEditKeyAction = 'save' | 'cancel' | 'insert-mention' | 'dismiss-mention'

export function resolveMessageEditKeydown(
  event: {
    key: string
    shiftKey: boolean
    ctrlKey: boolean
    metaKey: boolean
  },
  mentionOpen: boolean
): MessageEditKeyAction | null {
  if (mentionOpen) {
    if (event.key === 'Enter' && !event.shiftKey) {
      return 'insert-mention'
    }
    if (event.key === 'Escape') {
      return 'dismiss-mention'
    }
  }
  if (event.key === 'Escape') {
    return 'cancel'
  }
  const modifierEnter = event.key === 'Enter' && (event.ctrlKey || event.metaKey)
  if (modifierEnter || (event.key === 'Enter' && !event.shiftKey)) {
    return 'save'
  }
  return null
}
