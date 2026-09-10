import { describe, expect, it } from 'vitest'

import type { ActiveEditor } from '@/composables/workshop/useWorkshopTypes'
import {
  applyActiveEditorPresence,
  purgeActiveEditorsForUser,
  shouldFlashStructuralLock,
} from '@/composables/workshop/applyCollabEditorPresence'

function alice(): ActiveEditor {
  return { user_id: 1, username: 'Alice', color: '#f00', emoji: '1F' }
}

function bob(): ActiveEditor {
  return { user_id: 2, username: 'Bob', color: '#0f0', emoji: '2F' }
}

describe('applyActiveEditorPresence', () => {
  it('sets a lock when the node is free', () => {
    const editors = new Map<string, ActiveEditor>()
    const result = applyActiveEditorPresence(
      editors,
      {
        nodeId: 'n1',
        editing: true,
        userId: 1,
        username: 'Alice',
        color: '#f00',
        emoji: '1F',
      },
      (_id, name) => name ?? 'Alice'
    )
    expect(result.changed).toBe(true)
    expect(result.editor?.user_id).toBe(1)
    expect(editors.get('n1')?.username).toBe('Alice')
  })

  it('does not let another user overwrite an exclusive claim', () => {
    const editors = new Map<string, ActiveEditor>([['n1', alice()]])
    const result = applyActiveEditorPresence(
      editors,
      {
        nodeId: 'n1',
        editing: true,
        userId: 2,
        username: 'Bob',
        color: '#0f0',
        emoji: '2F',
      },
      (_id, name) => name ?? 'Bob'
    )
    expect(result.changed).toBe(false)
    expect(editors.get('n1')?.user_id).toBe(1)
  })

  it('does not clear Alice when Bob sends editing:false', () => {
    const editors = new Map<string, ActiveEditor>([['n1', alice()]])
    const result = applyActiveEditorPresence(
      editors,
      { nodeId: 'n1', editing: false, userId: 2 },
      () => 'Bob'
    )
    expect(result.changed).toBe(false)
    expect(editors.get('n1')?.user_id).toBe(1)
  })

  it('clears the lock when the holder releases', () => {
    const editors = new Map<string, ActiveEditor>([['n1', alice()]])
    const result = applyActiveEditorPresence(
      editors,
      { nodeId: 'n1', editing: false, userId: 1 },
      () => 'Alice'
    )
    expect(result.changed).toBe(true)
    expect(result.editor).toBeNull()
    expect(editors.has('n1')).toBe(false)
  })

  it('ignores an incomplete editing:true frame so it cannot wipe a lock', () => {
    const editors = new Map<string, ActiveEditor>([['n1', alice()]])
    const result = applyActiveEditorPresence(
      editors,
      { nodeId: 'n1', editing: true, userId: 1 },
      () => 'Alice'
    )
    expect(result.changed).toBe(false)
    expect(editors.get('n1')?.user_id).toBe(1)
  })
})

describe('purgeActiveEditorsForUser', () => {
  it('releases only that user and leaves other holders', () => {
    const editors = new Map<string, ActiveEditor>([
      ['n1', alice()],
      ['n2', bob()],
      ['n3', alice()],
    ])
    expect(purgeActiveEditorsForUser(editors, 1)).toEqual(['n1', 'n3'])
    expect(editors.has('n1')).toBe(false)
    expect(editors.get('n2')?.user_id).toBe(2)
    expect(editors.has('n3')).toBe(false)
  })
})

describe('shouldFlashStructuralLock', () => {
  const base = {
    workshopActive: true,
    nodeId: 'n1',
    recentlyClosed: false,
    textEditorOpen: false,
    holderUserId: null as number | null,
    currentUserId: 1,
  }

  it('flashes a free node', () => {
    expect(shouldFlashStructuralLock(base)).toBe(true)
  })

  it('skips a node whose text editor is still open', () => {
    expect(shouldFlashStructuralLock({ ...base, textEditorOpen: true })).toBe(false)
  })

  it('skips a node someone else already holds', () => {
    expect(shouldFlashStructuralLock({ ...base, holderUserId: 2 })).toBe(false)
  })

  it('skips the close-cooldown window', () => {
    expect(shouldFlashStructuralLock({ ...base, recentlyClosed: true })).toBe(false)
  })
})
