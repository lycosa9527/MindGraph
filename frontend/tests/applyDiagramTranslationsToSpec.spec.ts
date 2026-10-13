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

  it('keeps the second language line and retargets the primary language', () => {
    const spec = {
      type: 'mindmap',
      languages: { primary: 'zh', secondary: 'en' },
      nodes: [
        {
          id: 'n1',
          text: '光',
          textSecondary: 'Light',
          data: { label: '光', labelSecondary: 'Light' },
        },
      ],
      _mindmap_summaries: [{ id: 's1', text: '概要', textSecondary: 'Summary' }],
    }
    const next = applyDiagramTranslationsToSpec(
      spec,
      [
        { itemId: 'n1', kind: 'node', text: 'lys' },
        { itemId: 'smry:s1', kind: 'node', text: 'sammendrag' },
      ],
      'no'
    )
    expect(next.languages).toEqual({ primary: 'no', secondary: 'en' })
    const node = (next.nodes as Array<Record<string, unknown>>)[0]
    expect(node.text).toBe('lys')
    expect(node.textSecondary).toBe('Light')
    expect(node.data).toEqual({ label: 'lys', labelSecondary: 'Light' })
    expect(next._mindmap_summaries).toEqual([
      { id: 's1', text: 'sammendrag', textSecondary: 'Summary' },
    ])
  })
})
