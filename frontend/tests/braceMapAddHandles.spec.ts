import { describe, expect, it } from 'vitest'

import {
  braceChildIds,
  braceParentId,
  layoutBraceMapAddHandles,
  resolveBraceMapAddSelectionKind,
} from '@/utils/braceMapAddHandles'
import { BRACE_DIMENSION_LABEL_ID, BRACE_WHOLE_NODE_ID } from '@/utils/braceMapIdentity'

const rect = {
  left: 100,
  top: 200,
  right: 220,
  bottom: 260,
  width: 120,
  height: 60,
}

describe('braceMapAddHandles', () => {
  it('resolves the whole, a member, and skips the dimension label', () => {
    expect(resolveBraceMapAddSelectionKind({ id: BRACE_WHOLE_NODE_ID, type: 'topic' })).toBe(
      'whole'
    )
    expect(resolveBraceMapAddSelectionKind({ id: 'part-1', type: 'brace' })).toBe('member')
    expect(
      resolveBraceMapAddSelectionKind({ id: BRACE_DIMENSION_LABEL_ID, type: 'label' })
    ).toBeNull()
  })

  it('places a right handle on the whole and top, right, and bottom handles on a member', () => {
    expect(layoutBraceMapAddHandles('whole', rect)).toEqual([
      { action: 'child-append', left: 220, top: 230 },
    ])
    expect(layoutBraceMapAddHandles('member', rect)).toEqual([
      { action: 'sibling-before', left: 160, top: 200 },
      { action: 'child-append', left: 220, top: 230 },
      { action: 'sibling-after', left: 160, top: 260 },
    ])
  })

  it('reads sibling order from connection order', () => {
    const connections = [
      { source: 'whole', target: 'b' },
      { source: 'other', target: 'x' },
      { source: 'whole', target: 'a' },
    ]
    expect(braceChildIds('whole', connections)).toEqual(['b', 'a'])
    expect(braceParentId('a', connections)).toBe('whole')
    expect(braceParentId('missing', connections)).toBeNull()
  })
})
