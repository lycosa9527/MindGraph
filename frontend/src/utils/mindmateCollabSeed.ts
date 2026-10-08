/**
 * Turn a MindMate library thread into collab room seed messages.
 * The start API accepts at most 100 messages, so only the newest fit.
 */

export interface CollabSeedDraft {
  role: 'user' | 'assistant'
  content: string
}

export const COLLAB_SEED_MESSAGE_LIMIT = 100

interface DifyThreadTurn {
  query?: string
  answer?: string
}

export function difyMessagesToCollabSeed(
  messages: DifyThreadTurn[],
  displayQuery: (query: string) => string
): CollabSeedDraft[] {
  const seed: CollabSeedDraft[] = []
  for (const message of messages) {
    const query = displayQuery(message.query || '').trim()
    if (query) {
      seed.push({ role: 'user', content: query })
    }
    const answer = (message.answer || '').trim()
    if (answer) {
      seed.push({ role: 'assistant', content: answer })
    }
  }
  if (seed.length <= COLLAB_SEED_MESSAGE_LIMIT) {
    return seed
  }
  return seed.slice(seed.length - COLLAB_SEED_MESSAGE_LIMIT)
}
