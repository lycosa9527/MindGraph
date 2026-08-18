import { describe, expect, it } from 'vitest'

import { resolveVoiceNodeId } from '@/composables/editor/diagramVoiceMutations'
import type { DiagramNode } from '@/types'

function uuidCanvas(): DiagramNode[] {
  return [
    { id: 'topic', type: 'topic', text: 'Cars' },
    { id: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', type: 'branch', text: 'DIY' },
    { id: 'ffffffff-1111-4222-8333-444444444444', type: 'branch', text: 'Engine' },
  ]
}

describe('resolveVoiceNodeId', () => {
  it('does not map mind-map branch_N to L1 connection order', () => {
    const nodes = uuidCanvas()
    expect(resolveVoiceNodeId('mindmap', 'branch_0', nodes)).toBeNull()
    expect(resolveVoiceNodeId('mindmap', 'branch_1', nodes)).toBeNull()
  })

  it('still resolves leftover branch_N via identity alias', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', type: 'topic', text: 'Cars' },
      {
        id: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
        type: 'branch',
        text: 'DIY',
        data: { mindMapLegacyId: 'branch_0' },
      },
    ]
    expect(resolveVoiceNodeId('mindmap', 'branch_0', nodes)).toBe(
      'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
    )
  })
})
