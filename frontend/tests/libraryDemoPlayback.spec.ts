import { describe, expect, it } from 'vitest'

import {
  readDemoCaptionStore,
  sanitizeDemoCaptionHtml,
  seedDemoCaption,
} from '@/composables/demo/demoCaptionDefaults'
import { readDemoListStore, upsertDemoList } from '@/composables/demo/demoLists'
import {
  DEMO_HOLD_MS,
  DEMO_TEMPLATE_MS,
  demoHeroIdForSlide,
  demoPhaseAfter,
  demoShouldAdvance,
} from '@/composables/demo/demoPlayback'
import { beatMs, buildDemoTour } from '@/composables/demo/demoTour'
import {
  parseLibraryDemoDocument,
  parseLibraryDemoThumbnails,
} from '@/composables/demo/libraryDemoApi'
import {
  demoThumbnailIsStale,
  demoThumbnailNeedsRender,
} from '@/composables/demo/useDemoListThumbnails'
import type { Connection, DiagramNode } from '@/types'

describe('library demo playback', () => {
  it('keeps the template for one second, then reveals the diagram', () => {
    expect(demoPhaseAfter(DEMO_TEMPLATE_MS - 1, false)).toBe('template')
    expect(demoPhaseAfter(DEMO_TEMPLATE_MS, false)).toBe('revealed')
    expect(demoPhaseAfter(0, true)).toBe('revealed')
  })

  it('advances only after the revealed diagram has held, and not while paused', () => {
    expect(demoShouldAdvance('template', DEMO_HOLD_MS, false)).toBe(false)
    expect(demoShouldAdvance('revealed', DEMO_HOLD_MS - 1, false)).toBe(false)
    expect(demoShouldAdvance('revealed', DEMO_HOLD_MS, false)).toBe(true)
    expect(demoShouldAdvance('revealed', DEMO_HOLD_MS, true)).toBe(false)
  })

  it('maps slide index onto the four login films and wraps', () => {
    expect(demoHeroIdForSlide(0)).toBe('01-awaken-cosmos')
    expect(demoHeroIdForSlide(1)).toBe('02-mind-leap')
    expect(demoHeroIdForSlide(2)).toBe('03-study-light')
    expect(demoHeroIdForSlide(3)).toBe('04-ai-lab')
    expect(demoHeroIdForSlide(4)).toBe('01-awaken-cosmos')
    expect(demoHeroIdForSlide(-1)).toBe('04-ai-lab')
  })

  it('keeps an edited caption and seeds a missing one from the diagram type', () => {
    const stored = readDemoCaptionStore(
      JSON.stringify({
        saved: { text: 'Edited line', fontSize: 22, fontFace: 'serif' },
        broken: { text: 1 },
      })
    )
    expect(stored.saved).toEqual({
      text: 'Edited line',
      fontSize: 22,
      fontFace: 'serif',
      fontColor: 'ink',
    })
    expect(stored.broken).toBeUndefined()

    const seeded = seedDemoCaption(
      'bubble_map',
      'Water',
      (key, params) => `${key}:${params.title}`,
      undefined
    )
    expect(seeded.text).toBe('sidebar.demo.caption.bubble_map:Water')
    expect(seeded.fontSize).toBe(18)

    const kept = seedDemoCaption('bubble_map', 'Water', () => 'unused', stored.saved)
    expect(kept.text).toBe('Edited line')
  })

  it('keeps lists and emphasis and drops scripts from caption html', () => {
    const clean = sanitizeDemoCaptionHtml(
      '<ul><li><strong>One</strong></li></ul><script>alert(1)</script><span style="font-size:18px;color:red">Hi</span><span style="color:#1c1917">Ink</span>'
    )
    expect(clean).toContain('<ul>')
    expect(clean).toContain('<strong>One</strong>')
    expect(clean).not.toContain('script')
    expect(clean).toContain('font-size:18px')
    expect(clean).not.toContain('color:red')
    expect(clean).toContain('color:#1c1917')
  })

  it('saves a named demo list and reloads it as the last selection', () => {
    const empty = readDemoListStore(null)
    const stored = upsertDemoList(empty, {
      id: 'list-1',
      name: 'Monday class',
      diagramIds: ['a', 'b'],
      captions: {},
    })
    const raw = JSON.stringify(stored)
    expect(readDemoListStore(raw)).toEqual({
      lists: [{ id: 'list-1', name: 'Monday class', diagramIds: ['a', 'b'], captions: {} }],
      lastId: 'list-1',
    })
    const renamed = upsertDemoList(stored, {
      id: 'list-1',
      name: 'Monday class',
      diagramIds: ['b'],
      captions: {},
    })
    expect(renamed.lists).toHaveLength(1)
    expect(renamed.lists[0]?.diagramIds).toEqual(['b'])
  })

  it('keeps caption text and type style on the saved demo list', () => {
    const caption = {
      text: 'Students compare the two rivers.',
      html: '<p><strong>Students compare the two rivers.</strong></p>',
      fontSize: 22 as const,
      fontFace: 'serif' as const,
      fontColor: 'ink' as const,
    }
    const loaded = readDemoListStore(
      JSON.stringify({
        lists: [
          {
            id: 'list-2',
            name: 'Rivers',
            diagramIds: ['d1'],
            captions: { d1: caption, bad: { text: 1 } },
          },
        ],
        lastId: 'list-2',
      })
    )
    expect(loaded.lists[0]?.captions.d1).toEqual(caption)
    expect(loaded.lists[0]?.captions.bad).toBeUndefined()
    expect(loaded.lastId).toBe('list-2')
  })

  it('reads notes and type style from a server demo document', () => {
    const caption = {
      text: 'Students compare the two rivers.',
      html: '<p><strong>Students compare the two rivers.</strong></p>',
      fontSize: 22 as const,
      fontFace: 'serif' as const,
      fontColor: 'ink' as const,
    }
    const document = parseLibraryDemoDocument({
      lists: [{ id: 'list-2', name: 'Rivers', diagramIds: ['d1'], captions: { d1: caption } }],
      lastId: 'list-2',
      captions: { d1: caption },
    })
    expect(document.lastId).toBe('list-2')
    expect(document.lists[0]?.captions.d1).toEqual(caption)
    expect(document.captions.d1?.fontFace).toBe('serif')
  })

  it('keeps an older list that was saved before captions were stored on it', () => {
    const loaded = readDemoListStore(
      JSON.stringify({
        lists: [{ id: 'old', name: 'Old deck', diagramIds: ['a'] }],
        lastId: 'old',
      })
    )
    expect(loaded.lists[0]?.diagramIds).toEqual(['a'])
    expect(loaded.lists[0]?.captions).toEqual({})
  })

  it('tours a mind map as overview, topic, then each branch with its children', () => {
    const beats = buildDemoTour('mindmap', mindMapNodes(), mindMapEdges())
    expect(beats.map((beat) => beat.kind)).toEqual(['overview', 'group', 'group', 'group'])
    expect(beats[0]?.focusNodeId).toBeNull()
    expect(beats[1]?.nodeIds).toEqual(['topic'])
    expect(beats[1]?.focusNodeId).toBe('topic')
    expect(beats[2]?.nodeIds.sort()).toEqual(['a', 'a1'])
    expect(beats[2]?.focusNodeId).toBe('a')
    expect(beats[3]?.nodeIds.sort()).toEqual(['b', 'b1', 'b2'])
    expect(beats[3]?.ms).toBeGreaterThan(beats[2]?.ms ?? 0)
    expectInClamp(beats)
  })

  it('tours circle satellites clockwise from the top and skips the boundary', () => {
    const beats = buildDemoTour('circle_map', circleNodes(), [])
    expect(beats.map((beat) => beat.focusNodeId)).toEqual([null, 'top', 'right', 'bottom'])
    expect(beats.slice(1).some((beat) => beat.nodeIds.includes('ring'))).toBe(false)
    expect(beats[0]?.nodeIds).toContain('ring')
    expectInClamp(beats)
  })

  it('tours each flow step together with its substeps, left to right', () => {
    const beats = buildDemoTour('flow_map', flowNodes(), [
      { id: 'e1', source: 's1', target: 'sub' },
      { id: 'e2', source: 's1', target: 's2' },
    ])
    expect(beats[1]?.nodeIds.sort()).toEqual(['s1', 'sub'])
    expect(beats[1]?.focusNodeId).toBe('s1')
    expect(beats[2]?.nodeIds).toEqual(['s2'])
    expect(beats[2]?.ms).toBeLessThan(beats[1]?.ms ?? 0)
    expectInClamp(beats)
  })

  it('holds longer text and larger groups longer, inside the dwell clamps', () => {
    expect(beatMs(80, 1, 'group')).toBeGreaterThan(beatMs(1, 1, 'group'))
    expect(beatMs(4, 5, 'group')).toBeGreaterThan(beatMs(4, 1, 'group'))
    expect(beatMs(0, 0, 'overview')).toBe(2500)
    expect(beatMs(10000, 100, 'overview')).toBe(6000)
    expect(beatMs(0, 1, 'group')).toBe(1400)
    expect(beatMs(10000, 40, 'group')).toBe(5500)
  })

  it('keeps a fresh list thumbnail and refreshes one after the diagram changes', () => {
    const stored = parseLibraryDemoThumbnails({
      'diagram-1': {
        url: '/api/auth/library-demo/thumbnails/diagram-1',
        updatedAt: '2026-09-30T00:00:00Z',
      },
      bad: { url: 'https://example.test/x.png', updatedAt: '2026-09-30T00:00:00Z' },
    })
    expect(stored['diagram-1']?.url).toContain('/diagram-1')
    expect(stored.bad).toBeUndefined()
    expect(demoThumbnailIsStale(stored['diagram-1'], '2026-09-30T00:00:00Z')).toBe(false)
    expect(demoThumbnailIsStale(stored['diagram-1'], '2026-09-30T01:00:00Z')).toBe(true)
    expect(demoThumbnailIsStale(undefined, '2026-09-30T01:00:00Z')).toBe(true)
    const covered = parseLibraryDemoThumbnails({
      'diagram-2': { updatedAt: '2026-09-30T00:00:00Z' },
    })
    expect(covered['diagram-2']?.url).toBe('')
    expect(
      demoThumbnailNeedsRender(undefined, '2026-09-30T00:00:00Z', 'data:image/png;base64,abc')
    ).toBe(false)
    expect(
      demoThumbnailNeedsRender(
        covered['diagram-2'],
        '2026-09-30T00:00:00Z',
        'data:image/png;base64,abc'
      )
    ).toBe(false)
    expect(
      demoThumbnailNeedsRender(
        covered['diagram-2'],
        '2026-09-30T01:00:00Z',
        'data:image/png;base64,abc'
      )
    ).toBe(true)
    expect(demoThumbnailNeedsRender(undefined, '2026-09-30T00:00:00Z', null)).toBe(true)
  })
})

function node(
  id: string,
  text: string,
  type: DiagramNode['type'],
  x: number,
  y: number
): DiagramNode {
  return { id, text, type, position: { x, y } }
}

function mindMapNodes(): DiagramNode[] {
  return [
    node('topic', 'Topic', 'topic', 0, 0),
    node('a', 'A', 'branch', 120, -40),
    node('a1', 'child', 'branch', 220, -40),
    node('b', 'A much longer branch label', 'branch', 120, 40),
    node('b1', 'one', 'branch', 220, 10),
    node('b2', 'two', 'branch', 220, 70),
  ]
}

function mindMapEdges(): Connection[] {
  return [
    { id: 'e1', source: 'topic', target: 'a' },
    { id: 'e2', source: 'a', target: 'a1' },
    { id: 'e3', source: 'topic', target: 'b' },
    { id: 'e4', source: 'b', target: 'b1' },
    { id: 'e5', source: 'b', target: 'b2' },
  ]
}

function circleNodes(): DiagramNode[] {
  return [
    node('c', 'Center', 'center', 0, 0),
    node('top', 'North', 'bubble', 0, -100),
    node('right', 'East', 'bubble', 100, 0),
    node('bottom', 'South', 'bubble', 0, 100),
    node('ring', '', 'boundary', -200, -200),
  ]
}

function flowNodes(): DiagramNode[] {
  return [
    node('s1', 'Mix', 'flow', 0, 0),
    node('sub', 'Stir slowly until the batter is smooth', 'flowSubstep', 0, 50),
    node('s2', 'Bake', 'flow', 240, 0),
  ]
}

function expectInClamp(beats: { kind: string; ms: number }[]): void {
  for (const beat of beats) {
    const min = beat.kind === 'overview' ? 2500 : 1400
    const max = beat.kind === 'overview' ? 6000 : 5500
    expect(beat.ms).toBeGreaterThanOrEqual(min)
    expect(beat.ms).toBeLessThanOrEqual(max)
  }
}
