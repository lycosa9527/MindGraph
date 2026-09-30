/** Display helpers for MindMate seminar (collab) message rows. */
import {
  hasGeneratedDiagramImage,
  parseMindmateDiagramLibraryId,
  stripMindmateDiagramIdComments,
} from '@/utils/mindmateDiagramMeta'
import { isTeachingInstructionReply } from '@/utils/mindmateTeachingDesignFlag'

export interface CollabDisplayMessage {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}

/** Assistant markdown shown in the bubble — hide reply-kind / diagram-id markers. */
export function displayMindmateCollabContent(
  content: string,
  role: CollabDisplayMessage['role']
): string {
  if (role !== 'assistant') {
    return content || ''
  }
  return stripMindmateDiagramIdComments(content)
}

export function shouldShowCollabWordTemplateExport(message: CollabDisplayMessage): boolean {
  return (
    message.role === 'assistant' &&
    !message.streaming &&
    isTeachingInstructionReply(message.content)
  )
}

export function collabAssistantLibraryDiagramId(message: CollabDisplayMessage): string | null {
  if (message.role !== 'assistant' || message.streaming) {
    return null
  }
  return parseMindmateDiagramLibraryId(message.content)
}

/** Finished MindMate reply that includes a diagram the viewer can open on the canvas. */
export function collabAssistantOffersCanvasEdit(message: CollabDisplayMessage): boolean {
  if (message.role !== 'assistant' || message.streaming) {
    return false
  }
  if (parseMindmateDiagramLibraryId(message.content)) {
    return true
  }
  return hasGeneratedDiagramImage(message.content)
}

export function previousCollabUserPrompt(
  messages: readonly Pick<CollabDisplayMessage, 'role' | 'content'>[],
  assistantIndex: number
): string | undefined {
  for (let index = assistantIndex - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === 'user') {
      const prompt = messages[index].content?.trim()
      return prompt || undefined
    }
  }
  return undefined
}

export interface MindmateCollabTranscriptRow {
  id?: number
  role: 'user' | 'assistant'
  content: string
  sender_user_id?: number | null
  username?: string | null
  streaming?: boolean
  clientKey?: string
}

/**
 * Apply a join snapshot without erasing lines already on screen,
 * a live line that arrived ahead of the snapshot, or an optimistic send
 * that is not in the snapshot yet.
 */
export function mergeMindmateCollabSnapshot<T extends MindmateCollabTranscriptRow>(
  current: readonly T[],
  snapshot: readonly T[]
): T[] {
  const snapshotIds = new Set<number>()
  const persistedUserKeys = new Set<string>()
  for (const row of snapshot) {
    if (row.id != null) {
      snapshotIds.add(row.id)
    }
    if (row.role === 'user') {
      persistedUserKeys.add(`${row.sender_user_id ?? ''}:${row.content}`)
    }
  }
  const retained = current.filter((item) => item.id != null && !snapshotIds.has(item.id))
  const optimistic = current.filter((item) => {
    if (item.role !== 'user' || item.id != null || !item.clientKey) {
      return false
    }
    return !persistedUserKeys.has(`${item.sender_user_id ?? ''}:${item.content}`)
  })
  const numbered = [...snapshot.map((row) => ({ ...row })), ...retained.map((row) => ({ ...row }))]
  numbered.sort((left, right) => (left.id ?? 0) - (right.id ?? 0))
  return [...numbered, ...optimistic.map((row) => ({ ...row }))]
}

/** Prefer the finished assistant text when streamed chunks are only a prefix. */
export function resolveCollabAssistantEndContent(current: string, endContent: string): string {
  if (!endContent) {
    return current
  }
  if (!current || endContent.startsWith(current)) {
    return endContent
  }
  return current
}

export function collabMessageRowKey(
  message: { id?: number; clientKey?: string; role: string },
  index: number
): string {
  if (message.id != null) {
    return `id-${message.id}`
  }
  if (message.clientKey) {
    return message.clientKey
  }
  return `msg-${index}-${message.role}`
}

export type CollabFeedbackRating = 'like' | 'dislike' | null

export function nextCollabFeedback(
  current: CollabFeedbackRating | undefined,
  clicked: 'like' | 'dislike'
): CollabFeedbackRating {
  return current === clicked ? null : clicked
}

export function lastFinishedAssistantIndex(
  messages: readonly Pick<CollabDisplayMessage, 'role' | 'streaming'>[]
): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const row = messages[index]
    if (row?.role === 'assistant' && !row.streaming) {
      return index
    }
  }
  return -1
}

export function collabMessagesForShareExport(
  rows: readonly (CollabDisplayMessage & { id?: number; clientKey?: string })[]
): Array<{ id: string; role: 'user' | 'assistant'; content: string; timestamp: number }> {
  return rows
    .filter((row) => !row.streaming)
    .map((row, index) => ({
      id: collabMessageRowKey(row, index),
      role: row.role,
      content: displayMindmateCollabContent(row.content, row.role),
      timestamp: Date.now(),
    }))
}
