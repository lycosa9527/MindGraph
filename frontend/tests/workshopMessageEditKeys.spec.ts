import { describe, expect, it } from 'vitest'

import { resolveMessageEditKeydown } from '@/utils/workshopMessageEditKeys'

function key(
  name: string,
  mods: { shiftKey?: boolean; ctrlKey?: boolean; metaKey?: boolean } = {}
): {
  key: string
  shiftKey: boolean
  ctrlKey: boolean
  metaKey: boolean
} {
  return {
    key: name,
    shiftKey: mods.shiftKey === true,
    ctrlKey: mods.ctrlKey === true,
    metaKey: mods.metaKey === true,
  }
}

describe('resolveMessageEditKeydown', () => {
  it('saves on Enter, matching compose Enter-to-send', () => {
    expect(resolveMessageEditKeydown(key('Enter'), false)).toBe('save')
  })

  it('saves on Ctrl+Enter and Cmd+Enter', () => {
    expect(resolveMessageEditKeydown(key('Enter', { ctrlKey: true }), false)).toBe('save')
    expect(resolveMessageEditKeydown(key('Enter', { metaKey: true }), false)).toBe('save')
  })

  it('leaves Shift+Enter for a newline', () => {
    expect(resolveMessageEditKeydown(key('Enter', { shiftKey: true }), false)).toBeNull()
  })

  it('cancels on Escape', () => {
    expect(resolveMessageEditKeydown(key('Escape'), false)).toBe('cancel')
  })

  it('inserts or dismisses mention before save/cancel', () => {
    expect(resolveMessageEditKeydown(key('Enter'), true)).toBe('insert-mention')
    expect(resolveMessageEditKeydown(key('Escape'), true)).toBe('dismiss-mention')
  })
})
