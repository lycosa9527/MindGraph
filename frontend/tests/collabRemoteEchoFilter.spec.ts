import { describe, expect, it } from 'vitest'

import {
  applyForeignLockToOutboundConnections,
  applyForeignLockToOutboundNodes,
  asReadonlyIdSet,
  layoutPatchForLockedNode,
} from '@/utils/collabRemoteEchoFilter'

describe('collabRemoteEchoFilter', () => {
  it('strips text from a foreign-locked node and keeps position', () => {
    expect(
      layoutPatchForLockedNode({
        id: 'locked',
        text: 'stale',
        position: { x: 12, y: 40 },
      })
    ).toEqual({ id: 'locked', position: { x: 12, y: 40 } })
    expect(
      applyForeignLockToOutboundNodes(
        [
          { id: 'locked', text: 'stale', position: { x: 12, y: 40 } },
          { id: 'free', text: 'ok' },
        ],
        new Set(['locked'])
      )
    ).toEqual([
      { id: 'locked', position: { x: 12, y: 40 } },
      { id: 'free', text: 'ok' },
    ])
  })

  it('treats a missing or non-Set lock list as empty', () => {
    expect(asReadonlyIdSet(undefined).size).toBe(0)
    expect(asReadonlyIdSet({ has: () => true }).size).toBe(0)
    expect(asReadonlyIdSet(new Set(['a'])).has('a')).toBe(true)
  })

  it('drops a locked-target connection so add-child to an edited node is blocked', () => {
    expect(
      applyForeignLockToOutboundConnections(
        [
          { id: 'e1', source: 'parent', target: 'locked' },
          { id: 'e2', source: 'parent', target: 'child' },
        ],
        new Set(['locked'])
      )
    ).toEqual([{ id: 'e2', source: 'parent', target: 'child' }])
  })
})
