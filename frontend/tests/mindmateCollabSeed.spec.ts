import { describe, expect, it } from 'vitest'

import {
  COLLAB_SEED_MESSAGE_LIMIT,
  difyMessagesToCollabSeed,
} from '../src/utils/mindmateCollabSeed'

describe('difyMessagesToCollabSeed', () => {
  it('pairs each turn into user and assistant messages', () => {
    const seed = difyMessagesToCollabSeed(
      [
        { query: '  hello  ', answer: 'hi' },
        { query: '', answer: '   ' },
        { query: 'next', answer: '' },
      ],
      (query) => query
    )
    expect(seed).toEqual([
      { role: 'user', content: 'hello' },
      { role: 'assistant', content: 'hi' },
      { role: 'user', content: 'next' },
    ])
  })

  it('keeps the newest messages when the thread exceeds the room limit', () => {
    const messages = Array.from({ length: 60 }, (_, index) => ({
      query: `q${index}`,
      answer: `a${index}`,
    }))
    const seed = difyMessagesToCollabSeed(messages, (query) => query)
    expect(seed).toHaveLength(COLLAB_SEED_MESSAGE_LIMIT)
    expect(seed[0]).toEqual({ role: 'user', content: 'q10' })
    expect(seed[seed.length - 1]).toEqual({ role: 'assistant', content: 'a59' })
  })
})
