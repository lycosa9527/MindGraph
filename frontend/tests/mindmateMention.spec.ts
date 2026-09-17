import { describe, expect, it } from 'vitest'

import {
  contentMentionsMindmate,
  filterMentionCandidates,
  findMentionQueryAtCaret,
  insertMentionToken,
} from '@/utils/mindmateMention'

describe('mindmateMention', () => {
  it('detects an @ query at the caret', () => {
    expect(findMentionQueryAtCaret('你好 @Min', 7)).toEqual({ at: 3, query: 'Min' })
    expect(findMentionQueryAtCaret('a@Min', 5)).toBeNull()
    expect(findMentionQueryAtCaret('plain', 5)).toBeNull()
  })

  it('inserts an @Name token and moves the caret', () => {
    const next = insertMentionToken('问 @Mind', 7, 'MindMate')
    expect(next.text).toBe('问 @MindMate ')
    expect(next.caret).toBe('问 @MindMate '.length)
  })

  it('filters candidates by name', () => {
    const rows = filterMentionCandidates(
      [
        { id: 'agent-mindmate', name: 'MindMate', kind: 'agent' },
        { id: 'user-1', name: '王老师', kind: 'user' },
      ],
      'mind'
    )
    expect(rows.map((row) => row.id)).toEqual(['agent-mindmate'])
  })

  it('detects MindMate mentions including bold and school aliases', () => {
    expect(contentMentionsMindmate('@MindMate 帮我写教案')).toBe(true)
    expect(contentMentionsMindmate('@**MindMate** 帮我写教案')).toBe(true)
    expect(contentMentionsMindmate('@迈特教研 帮我写教案', ['迈特教研'])).toBe(true)
    expect(contentMentionsMindmate('只给老师看')).toBe(false)
    expect(contentMentionsMindmate('@mindmatexyz')).toBe(false)
  })
})
