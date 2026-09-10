/**
 * Apply inbound node-lock presence without letting a structural flash or
 * another user's release wipe an exclusive text-edit claim.
 */
import type { ActiveEditor } from './useWorkshopTypes'

export interface CollabEditorPresenceInput {
  nodeId: string
  editing: boolean
  userId?: number
  username?: string
  color?: string
  emoji?: string
}

export interface CollabEditorPresenceResult {
  changed: boolean
  editor: ActiveEditor | null
}

export function applyActiveEditorPresence(
  editors: Map<string, ActiveEditor>,
  input: CollabEditorPresenceInput,
  resolveUsername: (userId: number, username?: string) => string
): CollabEditorPresenceResult {
  const existing = editors.get(input.nodeId) ?? null

  if (input.editing) {
    if (input.userId == null || !input.color || !input.emoji) {
      return { changed: false, editor: existing }
    }
    if (existing && existing.user_id !== input.userId) {
      return { changed: false, editor: existing }
    }
    const editor: ActiveEditor = {
      user_id: input.userId,
      username: resolveUsername(input.userId, input.username),
      color: input.color,
      emoji: input.emoji,
    }
    editors.set(input.nodeId, editor)
    return { changed: true, editor }
  }

  if (!existing) {
    return { changed: false, editor: null }
  }
  if (input.userId != null && existing.user_id !== input.userId) {
    return { changed: false, editor: existing }
  }
  editors.delete(input.nodeId)
  return { changed: true, editor: null }
}

export function purgeActiveEditorsForUser(
  editors: Map<string, ActiveEditor>,
  userId: number
): string[] {
  const released: string[] = []
  for (const [nodeId, editor] of editors) {
    if (editor.user_id === userId) {
      released.push(nodeId)
    }
  }
  for (const nodeId of released) {
    editors.delete(nodeId)
  }
  return released
}

export function shouldFlashStructuralLock(options: {
  workshopActive: boolean
  nodeId: string
  recentlyClosed: boolean
  textEditorOpen: boolean
  holderUserId: number | null
  currentUserId: number
}): boolean {
  if (!options.workshopActive || !options.nodeId) {
    return false
  }
  if (options.recentlyClosed || options.textEditorOpen) {
    return false
  }
  if (options.holderUserId != null && options.holderUserId !== options.currentUserId) {
    return false
  }
  return true
}
