/**
 * MindMate active thread helpers — in-memory navigation restore (Pinia).
 *
 * Supersedes the legacy messageCache localStorage prefetch for the hot path
 * (MindMate → canvas → back). Prefetch cache remains for other use cases.
 */

export type FeedbackRating = 'like' | 'dislike' | null

export interface MindMateFile {
  id: string
  name: string
  type: 'image' | 'document' | 'audio' | 'video' | 'custom'
  size: number
  extension: string
  mime_type: string
  preview_url?: string
}

export interface MindMateMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  isStreaming?: boolean
  files?: MindMateFile[]
  difyMessageId?: string
  feedback?: FeedbackRating
}

export interface DifyHistoryMessage {
  id: string
  query?: string
  answer?: string
  created_at: number
  feedback?: FeedbackRating | { rating?: FeedbackRating | null } | null
}

export interface ActiveThreadSnapshot {
  conversationId: string
  messages: MindMateMessage[]
  hasGreeted: boolean
  updatedAt: number
}

function extractFeedback(raw: DifyHistoryMessage['feedback']): FeedbackRating | undefined {
  if (raw === 'like' || raw === 'dislike') {
    return raw
  }
  if (raw && typeof raw === 'object' && 'rating' in raw) {
    const rating = raw.rating
    if (rating === 'like' || rating === 'dislike') {
      return rating
    }
  }
  return undefined
}

/** Strip blob preview URLs and streaming flags before persisting in Pinia. */
export function sanitizeMessagesForStore(messages: MindMateMessage[]): MindMateMessage[] {
  return messages.map((msg) => {
    const sanitized: MindMateMessage = {
      ...msg,
      isStreaming: false,
    }
    if (msg.files?.length) {
      sanitized.files = msg.files.map((file) => {
        const { preview_url: _previewUrl, ...rest } = file
        return rest
      })
    }
    return sanitized
  })
}

export function cloneMindMateMessages(messages: readonly MindMateMessage[]): MindMateMessage[] {
  return sanitizeMessagesForStore(JSON.parse(JSON.stringify(messages)) as MindMateMessage[])
}

export function mapDifyMessagesToMindMate(difyMessages: DifyHistoryMessage[]): MindMateMessage[] {
  const result: MindMateMessage[] = []
  let seq = 0

  for (const msg of difyMessages) {
    const baseTs = msg.created_at * 1000
    if (msg.query) {
      result.push({
        id: `hist_user_${msg.id}_${seq}`,
        role: 'user',
        content: msg.query,
        timestamp: baseTs,
      })
      seq += 1
    }
    if (msg.answer) {
      const mapped: MindMateMessage = {
        id: `hist_asst_${msg.id}_${seq}`,
        role: 'assistant',
        content: msg.answer,
        timestamp: baseTs + 1,
        difyMessageId: msg.id,
      }
      const feedback = extractFeedback(msg.feedback)
      if (feedback) {
        mapped.feedback = feedback
      }
      result.push(mapped)
      seq += 1
    }
  }

  return result
}

export function threadsContentEqual(a: MindMateMessage[], b: MindMateMessage[]): boolean {
  if (a.length !== b.length) {
    return false
  }
  for (let i = 0; i < a.length; i += 1) {
    if (a[i].role !== b[i].role) {
      return false
    }
    if (a[i].content !== b[i].content) {
      return false
    }
  }
  return true
}

/**
 * Whether a Dify history fetch should replace the in-memory thread.
 * Rejects empty/partial server copies that lag behind the local Pinia thread.
 */
export function shouldApplyDifyHistory(
  local: MindMateMessage[],
  mapped: MindMateMessage[]
): boolean {
  if (mapped.length === 0 && local.length > 0) {
    return false
  }
  if (mapped.length < local.length) {
    return false
  }
  return !threadsContentEqual(local, mapped)
}
