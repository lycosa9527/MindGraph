import { afterEach, describe, expect, it } from 'vitest'

import {
  consumeKittyPendingDesktopExplain,
  peekKittyPendingDesktopExplain,
  shouldFlushKittyPendingDesktopExplain,
  stashKittyPendingDesktopExplain,
} from '@/composables/kitty/kittyPendingCanvasAction'

describe('kitty pending desktop explain', () => {
  afterEach(() => {
    sessionStorage.clear()
  })

  it('round-trips node + library and consumes the stash', () => {
    stashKittyPendingDesktopExplain('topic', 'lib-1')
    expect(peekKittyPendingDesktopExplain()).toEqual({
      nodeId: 'topic',
      libraryId: 'lib-1',
    })
    expect(consumeKittyPendingDesktopExplain()).toEqual({
      nodeId: 'topic',
      libraryId: 'lib-1',
    })
    expect(peekKittyPendingDesktopExplain()).toBeNull()
  })

  it('reads a legacy plain-string stash', () => {
    sessionStorage.setItem('mindgraph:kitty_pending_desktop_explain', 'branch-9')
    expect(peekKittyPendingDesktopExplain()).toEqual({ nodeId: 'branch-9' })
  })

  it('flushes only when the library matches and the node has a label', () => {
    const pending = { nodeId: 'topic', libraryId: 'lib-1' }
    const topic = { id: 'topic', text: '中国' }
    expect(shouldFlushKittyPendingDesktopExplain(pending, 'lib-2', [topic])).toBeNull()
    expect(shouldFlushKittyPendingDesktopExplain(pending, 'lib-1', [{ id: 'other', text: 'x' }])).toBeNull()
    expect(shouldFlushKittyPendingDesktopExplain(pending, 'lib-1', [{ id: 'topic', text: '  ' }])).toBeNull()
    expect(shouldFlushKittyPendingDesktopExplain(pending, 'lib-1', [topic])).toBe('topic')
    expect(shouldFlushKittyPendingDesktopExplain({ nodeId: 'topic' }, null, [topic])).toBe('topic')
  })
})
