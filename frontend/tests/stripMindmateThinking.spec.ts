import { describe, expect, it } from 'vitest'

import { stripMindmateThinkingBlocks } from '@/utils/stripMindmateThinking'

describe('stripMindmateThinkingBlocks', () => {
  it('removes think, thinking, and reasoning blocks', () => {
    const raw = 'Hello <think>hidden</think> <thinking>also</thinking> <reasoning>why</reasoning> there'
    const visible = stripMindmateThinkingBlocks(raw)
    expect(visible).not.toContain('hidden')
    expect(visible).not.toContain('also')
    expect(visible).not.toContain('why')
    expect(visible.startsWith('Hello')).toBe(true)
    expect(visible.endsWith('there')).toBe(true)
    expect(stripMindmateThinkingBlocks('<think>only</think>')).toBe('')
  })

  it('keeps the answer when no thinking tags are present', () => {
    expect(stripMindmateThinkingBlocks('Plain answer')).toBe('Plain answer')
  })
})