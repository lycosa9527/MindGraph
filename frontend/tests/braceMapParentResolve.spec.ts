/**
 * Brace map add: subparts must attach under the part group, not under another subpart.
 */
import { describe, expect, it } from 'vitest'

import {
  isBraceMapPartAddTarget,
  isBraceMapSubpartNode,
  resolveBraceMapSubpartAttachParentId,
} from '@/stores/diagram/braceMapParentResolve'
import type { Connection, DiagramNode } from '@/types'

const nodes: DiagramNode[] = [
  { id: 'topic', text: 'Whole', type: 'topic', position: { x: 0, y: 0 } },
  { id: 'part-a', text: 'Part A', type: 'brace', position: { x: 0, y: 0 } },
  { id: 'sub-a1', text: 'Sub A1', type: 'brace', position: { x: 0, y: 0 } },
]

const connections: Connection[] = [
  { id: 'e1', source: 'topic', target: 'part-a' },
  { id: 'e2', source: 'part-a', target: 'sub-a1' },
]

describe('resolveBraceMapSubpartAttachParentId', () => {
  it('keeps part id when selection is a direct child of root', () => {
    expect(resolveBraceMapSubpartAttachParentId('part-a', connections, 'topic')).toBe('part-a')
  })

  it('resolves subpart selection to its part group parent', () => {
    expect(resolveBraceMapSubpartAttachParentId('sub-a1', connections, 'topic')).toBe('part-a')
  })
})

describe('isBraceMapPartAddTarget', () => {
  it('treats root as part-add target', () => {
    const topic = nodes[0]
    expect(isBraceMapPartAddTarget('topic', topic, 'topic')).toBe(true)
  })

  it('treats part node as subpart-add target', () => {
    const part = nodes[1]
    expect(isBraceMapPartAddTarget('part-a', part, 'topic')).toBe(false)
  })
})

describe('isBraceMapSubpartNode', () => {
  it('identifies direct child of root as part, not subpart', () => {
    expect(isBraceMapSubpartNode('part-a', connections, 'topic')).toBe(false)
  })

  it('identifies nested child as subpart', () => {
    expect(isBraceMapSubpartNode('sub-a1', connections, 'topic')).toBe(true)
  })
})
