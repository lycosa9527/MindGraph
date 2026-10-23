import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode } from '@/types'
import {
  hostnameFromMindMapHref,
  mergeNodeAdornment,
  mindMapAdornmentDeletePatch,
  mindMapAdornmentStorageKeys,
  parseMindMapAdornments,
  remapMindMapAdornmentsAfterReload,
  resolveMindMapAdornmentParts,
  resolveMindMapLinkDisplayName,
  sanitizeMindMapHref,
  sanitizeMindMapImageUrl,
  seedMindMapLinkDialog,
  textWithIconAdornment,
} from '@/utils/mindMapAdornments'

describe('mind map adornments', () => {
  it('treats an icon as leading label text', () => {
    expect(textWithIconAdornment('属性5', null)).toBe('属性5')
    expect(textWithIconAdornment('属性5', { href: 'https://example.com' })).toBe('属性5')
    expect(textWithIconAdornment('属性5', { icon: '😬' })).toBe('😬 属性5')
    expect(textWithIconAdornment('', { icon: '😬' })).toBe('😬')
    expect(
      textWithIconAdornment('属性5', { icon: '😬', imageUrl: 'data:image/png;base64,aa' })
    ).toBe('😬 属性5')
  })

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

  it('seeds name above the URL and hides a full link on the node', () => {
    expect(seedMindMapLinkDialog('Wikipedia', 'https://en.wikipedia.org/wiki/X')).toEqual({
      name: 'Wikipedia',
      href: 'https://en.wikipedia.org/wiki/X',
      namePlaceholder: 'Wikipedia',
    })
    expect(seedMindMapLinkDialog('https://en.wikipedia.org/wiki/X', '')).toEqual({
      name: '',
      href: 'https://en.wikipedia.org/wiki/X',
      namePlaceholder: '',
    })
    expect(seedMindMapLinkDialog('子项1.1', '')).toEqual({
      name: '',
      href: '',
      namePlaceholder: '子项1.1',
    })
    expect(hostnameFromMindMapHref('https://www.example.com/path?q=1')).toBe('example.com')
    expect(
      resolveMindMapLinkDisplayName(
        '',
        'https://www.example.com/very/long',
        'https://www.example.com/very/long'
      )
    ).toBe('example.com')
    expect(
      resolveMindMapLinkDisplayName('Docs', 'https://example.com/a', 'https://example.com/a')
    ).toBe('Docs')
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

  it('deletes adornment layers link → image → icon', () => {
    expect(mindMapAdornmentDeletePatch({ href: 'https://a', icon: '⭐' })).toEqual({ href: '' })
    expect(mindMapAdornmentDeletePatch({ icon: '⭐', imageUrl: 'https://img/x.png' })).toEqual({
      imageUrl: '',
    })
    expect(mindMapAdornmentDeletePatch({ icon: '⭐' })).toEqual({ icon: '' })
  })

  it('lists path and legacy node-id storage keys', () => {
    const conns: Connection[] = [
      { id: 'e1', source: 'topic', target: 'a', sourceHandle: 'mindmap-right' },
    ]
    expect(mindMapAdornmentStorageKeys('topic', conns)).toEqual(['topic'])
    expect(mindMapAdornmentStorageKeys('a', conns)).toEqual(['r/0', 'a'])
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
