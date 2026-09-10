import { describe, expect, it } from 'vitest'

import { applyDiagramTranslationsToSpec } from '@/utils/applyDiagramTranslationsToSpec'

describe('applyDiagramTranslationsToSpec', () => {
  it('writes translated labels onto a cloned spec', () => {
    const spec = {
      type: 'mindmap',
      nodes: [
        { id: 'n1', text: '光', data: { label: '光' } },
        { id: 'n2', text: 'Keep' },
      ],
      connections: [{ id: 'c1', label: 'to' }],
    }
    const next = applyDiagramTranslationsToSpec(spec, [
      { itemId: 'n1', kind: 'node', text: 'Light' },
      { itemId: 'c1', kind: 'connection', text: 'vers' },
    ])
    expect(next).not.toBe(spec)
    expect(next).toEqual({
      type: 'mindmap',
      nodes: [
        { id: 'n1', text: 'Light', data: { label: 'Light' } },
        { id: 'n2', text: 'Keep' },
      ],
      connections: [{ id: 'c1', label: 'vers' }],
    })
    expect(spec.nodes[0].text).toBe('光')
  })
})
