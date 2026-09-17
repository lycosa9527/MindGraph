/** Display helpers for MindMate seminar (collab) message rows. */

import {
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
export function displayMindmateCollabContent(content: string, role: CollabDisplayMessage['role']): string {
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
  clicked: 'like' | 'dislike',
): CollabFeedbackRating {
  return current === clicked ? null : clicked
}

export function lastFinishedAssistantIndex(
  messages: readonly Pick<CollabDisplayMessage, 'role' | 'streaming'>[],
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
  rows: readonly (CollabDisplayMessage & { id?: number; clientKey?: string })[],
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
