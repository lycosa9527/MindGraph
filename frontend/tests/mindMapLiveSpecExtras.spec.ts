import { describe, expect, it } from 'vitest'

import {
  attachMindMapLiveSpecExtras,
  mergeMindMapPresentationExtrasIntoSpec,
  mindMapLiveSpecExtrasFingerprint,
  pickMindMapLiveSpecExtras,
} from '@/utils/mindMapLiveSpecExtras'
import { getKittyDiagramContentFingerprint } from '@/composables/kitty/kittyDiagramFingerprint'

describe('mindMapLiveSpecExtras', () => {
  it('picks only durable mindmap extras', () => {
    const picked = pickMindMapLiveSpecExtras({
      nodes: [{ id: 'topic' }],
      connections: [],
      _mindmap_diagram_style: 'classic',
      _mindmap_theme: 'ocean',
      _node_styles: { 'branch-r-1-0': { nodeShape: 'rounded' } },
      _collapsed_paths: ['r/0'],
      _mindmap_canvas: { v2: { theme: 'ocean' } },
      unrelated: true,
    })
    expect(picked).toEqual({
      _mindmap_diagram_style: 'classic',
      _mindmap_theme: 'ocean',
      _node_styles: { 'branch-r-1-0': { nodeShape: 'rounded' } },
      _collapsed_paths: ['r/0'],
      _mindmap_canvas: { v2: { theme: 'ocean' } },
    })
    expect('unrelated' in picked).toBe(false)
    expect('nodes' in picked).toBe(false)
  })

  it('attaches extras onto live-spec diagram_data', () => {
    const target: Record<string, unknown> = {
      nodes: [],
      connections: [],
    }
    attachMindMapLiveSpecExtras(target, {
      _mindmap_diagram_style: 'formal',
      _node_styles: { topic: { borderColor: '#123' } },
    })
    expect(target._mindmap_diagram_style).toBe('formal')
    expect(target._node_styles).toEqual({ topic: { borderColor: '#123' } })
    expect(target.nodes).toEqual([])
  })

  it('changes kitty fingerprint when only mindmap style extras change', () => {
    const base = {
      nodes: [{ id: 'topic', text: 'T' }],
      connections: [],
      _mindmap_diagram_style: 'classic',
    }
    const styled = {
      ...base,
      _mindmap_diagram_style: 'formal',
    }
    expect(getKittyDiagramContentFingerprint(base)).not.toBe(
      getKittyDiagramContentFingerprint(styled)
    )
    expect(mindMapLiveSpecExtrasFingerprint(base)).not.toBe(
      mindMapLiveSpecExtrasFingerprint(styled)
    )
  })

  it('changes kitty fingerprint when mindMapUid is first assigned', () => {
    const before = {
      nodes: [{ id: 'branch-r-1-0', text: '你好', data: { label: '你好' } }],
      connections: [],
    }
    const after = {
      nodes: [
        {
          id: 'branch-r-1-0',
          text: '你好',
          data: { label: '你好', mindMapUid: 'uid-1' },
        },
      ],
      connections: [],
    }
    expect(getKittyDiagramContentFingerprint(before)).not.toBe(
      getKittyDiagramContentFingerprint(after)
    )
  })

  it('merges presentation extras into LLM replace specs without node styles', () => {
    const incoming = {
      topic: 'T',
      children: [{ text: 'A' }],
      _mindmap_theme: 'from-llm',
    }
    const current = {
      _mindmap_theme: 'ocean',
      _mindmap_diagram_style: 'formal',
      _mindmap_canvas: { v2: { theme: 'ocean' } },
      _node_styles: { 'branch-r-1-0': { borderColor: '#f00' } },
      _collapsed_paths: ['r/0'],
    }
    const merged = mergeMindMapPresentationExtrasIntoSpec(incoming, current)
    expect(merged._mindmap_theme).toBe('ocean')
    expect(merged._mindmap_diagram_style).toBe('formal')
    expect(merged._mindmap_canvas).toEqual({ v2: { theme: 'ocean' } })
    expect(merged._node_styles).toBeUndefined()
    expect(merged._collapsed_paths).toBeUndefined()
    expect(merged.children).toEqual([{ text: 'A' }])
    // Original LLM theme key is overwritten; object identity only when no merge.
    expect(mergeMindMapPresentationExtrasIntoSpec(incoming, {})).toBe(incoming)
  })
})
