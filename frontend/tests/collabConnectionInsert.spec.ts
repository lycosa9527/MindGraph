import { describe, expect, it } from 'vitest'

import {
  collabConnectionInsertIndex,
  remapCollabConnectionEndpoints,
  spliceCollabConnection,
  stripCollabInsertAfterTarget,
} from '@/utils/collabConnectionInsert'

describe('collabConnectionInsert', () => {
  it('inserts after the prior sibling, not at list end', () => {
    const conns = [
      { id: 'e0', source: 'topic', target: 'a' },
      { id: 'e1', source: 'topic', target: 'b' },
      { id: 'e2', source: 'topic', target: 'c' },
    ]
    expect(
      collabConnectionInsertIndex(conns, {
        source: 'topic',
        target: 'new',
        insert_after_target: 'a',
      })
    ).toBe(1)
  })

  it('splices and strips the transport hint', () => {
    const conns = [
      { id: 'e0', source: 'topic', target: 'a' },
      { id: 'e1', source: 'topic', target: 'b' },
    ]
    spliceCollabConnection(conns, {
      id: 'e-new',
      source: 'topic',
      target: 'new',
      insert_after_target: 'a',
    })
    expect(conns.map((row) => row.target)).toEqual(['a', 'new', 'b'])
    expect(conns[1]).toEqual({ id: 'e-new', source: 'topic', target: 'new' })
  })

  it('remaps insert_after_target with source and target', () => {
    const aliases: Record<string, string> = {
      'branch-r-1-0': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
    }
    const remapped = remapCollabConnectionEndpoints(
      {
        id: 'e-new',
        source: 'topic',
        target: 'new',
        insert_after_target: 'branch-r-1-0',
      },
      (hint) => aliases[hint] ?? hint
    )
    expect(remapped.insert_after_target).toBe('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
    const conns = [
      { id: 'e0', source: 'topic', target: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee' },
      { id: 'e1', source: 'topic', target: 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff' },
    ]
    spliceCollabConnection(conns, remapped)
    expect(conns.map((row) => row.target)).toEqual([
      'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
      'new',
      'bbbbbbbb-cccc-dddd-eeee-ffffffffffff',
    ])
  })

  it('strips insert_after_target from an existing row', () => {
    expect(
      stripCollabInsertAfterTarget({
        id: 'e',
        source: 'topic',
        target: 'a',
        insert_after_target: 'x',
      })
    ).toEqual({ id: 'e', source: 'topic', target: 'a' })
  })
})