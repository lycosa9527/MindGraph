import { describe, expect, it } from 'vitest'

import {
  collabMessageMentionsMindmate,
  insertMindmateMention,
} from '@/utils/mindmateCollabMention'

describe('mindmateCollabMention', () => {
  it('detects @MindMate', () => {
    expect(collabMessageMentionsMindmate('@MindMate hello')).toBe(true)
    expect(collabMessageMentionsMindmate('plain chat')).toBe(false)
  })

  it('detects custom agent alias', () => {
    expect(collabMessageMentionsMindmate('@小思 你好', '小思')).toBe(true)
  })

  it('inserts mention with spacing', () => {
    expect(insertMindmateMention('', 'MindMate')).toBe('@MindMate ')
    expect(insertMindmateMention('Hi', 'MindMate')).toBe('Hi @MindMate ')
  })
})
