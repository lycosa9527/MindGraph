import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode } from '@/types'
import {
  mergeNodeAdornment,
  parseMindMapAdornments,
  remapMindMapAdornmentsAfterReload,
  resolveMindMapAdornmentParts,
  sanitizeMindMapHref,
  sanitizeMindMapImageUrl,
} from '@/utils/mindMapAdornments'

describe('mind map adornments', () => {
  it('places icon/link inline and keeps image above', () => {
    expect(resolveMindMapAdornmentParts('inline', true, true)).toEqual({
      image: false,
      inline: true,
    })
    expect(resolveMindMapAdornmentParts('image', true, true)).toEqual({
      image: true,
      inline: false,
    })
    expect(resolveMindMapAdornmentParts('all', true, true)).toEqual({
      image: true,
      inline: true,
    })
  })

  it('rejects javascript and data hrefs', () => {
    expect(sanitizeMindMapHref('javascript:alert(1)')).toBeNull()
    expect(sanitizeMindMapHref('data:text/html,hi')).toBeNull()
    expect(sanitizeMindMapHref('https://example.com/x')).toBe('https://example.com/x')
    expect(sanitizeMindMapHref('example.com/x')).toBe('https://example.com/x')
  })

  it('accepts http(s) and data-url images only', () => {
    expect(sanitizeMindMapImageUrl('https://cdn.example/a.png')).toBe('https://cdn.example/a.png')
    expect(sanitizeMindMapImageUrl('data:image/png;base64,abc')).toBe('data:image/png;base64,abc')
    expect(sanitizeMindMapImageUrl('javascript:alert(1)')).toBeNull()
  })

  it('merges and clears adornment fields', () => {
    const merged = mergeNodeAdornment({ icon: '🔥', href: 'https://a' }, { href: '', icon: '⭐' })
    expect(merged).toEqual({ icon: '⭐' })
    expect(mergeNodeAdornment({ icon: '🔥' }, { icon: '' })).toBeUndefined()
  })

  it('parses extras and remaps paths after a sibling delete', () => {
    const parsed = parseMindMapAdornments({
      'r/1': { icon: '🔥' },
      topic: { href: 'https://ok' },
    })
    expect(parsed.topic?.href).toBe('https://ok')

    const oldNodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic' },
      { id: 'a', text: 'A', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 1 } },
      { id: 'b', text: 'B', type: 'branch', data: { mindMapSide: 'right', mindMapDepth: 1 } },
    ]
    const oldConns: Connection[] = [
      { id: 'e1', source: 'topic', target: 'a', sourceHandle: 'mindmap-right' },
      { id: 'e2', source: 'topic', target: 'b', sourceHandle: 'mindmap-right' },
    ]
    const newNodes = oldNodes.filter((n) => n.id !== 'a')
    const newConns = oldConns.filter((c) => c.target !== 'a')
    const remapped = remapMindMapAdornmentsAfterReload(
      { 'r/1': { icon: '🔥' } },
      oldNodes,
      oldConns,
      newNodes,
      newConns,
      (oldId, _oN, _oC, next) => (next.some((n) => n.id === oldId) ? oldId : null)
    )
    expect(remapped['r/0']?.icon).toBe('🔥')
  })
})
