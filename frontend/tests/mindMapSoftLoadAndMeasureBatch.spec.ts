import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'

import { useMindMapLayoutSlice } from '@/stores/diagram/mindMapLayout'
import type { DiagramContext } from '@/stores/diagram/types'
import { loadSpecForDiagramType } from '@/stores/specLoader'
import { loadMindMapSpec } from '@/stores/specLoader/mindMap'
import { useUIStore } from '@/stores/ui'
import { mindMapLibraryLoadOptions } from '@/utils/mindMapLibraryLoadOptions'
import {
  beginMindMapLoadSession,
  beginMindMapSpecLoadSession,
  isMindMapLoadSessionActive,
  markMindMapLoadStage,
} from '@/utils/mindMapLoadDebug'
import {
  buildMindMapOrthogonalSiblingMap,
  mindMapOrthogonalSiblingGroupKey,
} from '@/utils/mindMapOrthogonalSiblings'

function makeLayoutCtx(scheduleMindMapRecalc = vi.fn()) {
  return {
    type: ref('mindmap' as const),
    mindMapTopicActualWidth: ref<number | null>(null),
    mindMapNodeWidths: ref<Record<string, number>>({}),
    mindMapNodeHeights: ref<Record<string, number>>({}),
    mindMapPreserveIncomingY: ref(false),
    mindMapBulkLoading: ref(false),
    data: ref(null),
    scheduleMindMapRecalc,
  } as unknown as DiagramContext
}

describe('mind-map soft load (preferLaidOutMindMapNodes)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      length: 0,
      key: vi.fn(() => null),
    })
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        onchange: null,
        addListener: vi.fn(),
        addEventListener: vi.fn(),
        removeListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    useUIStore().mindMapCanvasMode = 'legacy'
  })

  it('preserves stamped node positions when preferLaidOutMindMapNodes is set', () => {
    const initial = loadMindMapSpec({
      topic: '中心主题',
      children: [{ text: '分支1' }, { text: '分支2' }],
    })
    const stamped = {
      nodes: initial.nodes.map((n) => ({
        ...n,
        position: n.position ? { x: n.position.x + 10, y: n.position.y + 20 } : n.position,
      })),
      connections: initial.connections,
    }

    const soft = loadSpecForDiagramType(stamped, 'mindmap', {
      preferLaidOutMindMapNodes: true,
    })
    expect(soft.nodes.map((n) => n.id)).toEqual(stamped.nodes.map((n) => n.id))
    for (const node of soft.nodes) {
      const stampedNode = stamped.nodes.find((n) => n.id === node.id)
      expect(node.position).toEqual(stampedNode?.position)
    }

    const hard = loadSpecForDiagramType(stamped, 'mindmap')
    // Default path rebuilds layout from tree — does not keep the +10/+20 stamp.
    const softTopic = soft.nodes.find((n) => n.id === 'topic')
    const hardTopic = hard.nodes.find((n) => n.id === 'topic')
    expect(softTopic?.position).not.toEqual(hardTopic?.position)
  })

  it('falls back to loadMindMapSpec rebuild without preferLaidOutMindMapNodes', () => {
    const initial = loadMindMapSpec({
      topic: '主题',
      children: [{ text: 'A' }, { text: 'B' }],
    })
    const reloaded = loadSpecForDiagramType(
      { nodes: initial.nodes, connections: initial.connections },
      'mindmap'
    )
    expect(reloaded.nodes.some((n) => n.id === 'topic')).toBe(true)
    expect(reloaded.connections.length).toBeGreaterThan(0)
  })
})

describe('mindMapLibraryLoadOptions', () => {
  it('enables soft-load without preserving prior-session measures', () => {
    expect(
      mindMapLibraryLoadOptions('mindmap', {
        nodes: [{ id: 'topic' }],
        connections: [{ id: 'e1', source: 'topic', target: 'a' }],
      })
    ).toEqual({
      preferLaidOutMindMapNodes: true,
    })
  })

  it('returns undefined without laid-out graph or for non-mind-map types', () => {
    expect(mindMapLibraryLoadOptions('mindmap', { topic: 'x' })).toBeUndefined()
    expect(
      mindMapLibraryLoadOptions('circle_map', {
        nodes: [{ id: 'topic' }],
        connections: [],
      })
    ).toBeUndefined()
  })
})

describe('mind-map load debug sessions', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('keeps library session through first spec load, restarts on rapid switch', () => {
    const store: Record<string, string> = { mindmap_load_debug: '1' }
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => store[key] ?? null,
      setItem: (key: string, value: string) => {
        store[key] = value
      },
      removeItem: (key: string) => {
        delete store[key]
      },
      clear: () => {
        Object.keys(store).forEach((key) => delete store[key])
      },
      length: 0,
      key: () => null,
    })
    const info = vi.spyOn(console, 'info').mockImplementation(() => undefined)

    beginMindMapLoadSession('library')
    beginMindMapSpecLoadSession()
    markMindMapLoadStage('spec:load:start', { diagramType: 'mindmap' })
    expect(isMindMapLoadSessionActive()).toBe(true)
    // Still the library session — only one session:start so far besides library.
    expect(info.mock.calls.filter((c) => String(c[0]).includes('session:start')).length).toBe(1)

    beginMindMapSpecLoadSession()
    expect(info.mock.calls.filter((c) => String(c[0]).includes('session:start reason=spec')).length).toBe(
      1
    )

    info.mockRestore()
  })
})

describe('mind-map measure batch settle', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('coalesces ResizeObserver reports into one scheduleMindMapRecalc', () => {
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn(() => 1)
    )
    vi.stubGlobal(
      'cancelAnimationFrame',
      vi.fn(() => undefined)
    )
    vi.useFakeTimers()

    const scheduleMindMapRecalc = vi.fn()
    const ctx = makeLayoutCtx(scheduleMindMapRecalc)

    const slice = useMindMapLayoutSlice(ctx)
    slice.armMindMapMeasureBatch(3)
    expect(ctx.mindMapBulkLoading.value).toBe(true)
    slice.setMindMapNodeDimensions('a', 40, 20)
    slice.setMindMapNodeDimensions('b', 50, 22)
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    slice.setMindMapTopicMeasured(80, 40)
    expect(scheduleMindMapRecalc).toHaveBeenCalledTimes(1)
    expect(ctx.mindMapBulkLoading.value).toBe(false)
  })

  it('counts unique nodes even when seeded estimates match DOM', () => {
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn(() => 1)
    )
    vi.stubGlobal(
      'cancelAnimationFrame',
      vi.fn(() => undefined)
    )
    vi.useFakeTimers()

    const scheduleMindMapRecalc = vi.fn()
    const ctx = makeLayoutCtx(scheduleMindMapRecalc)
    // Simulate loadFromSpec seeding estimates before mounts.
    ctx.mindMapNodeWidths.value = { a: 40, b: 50, topic: 80 }
    ctx.mindMapNodeHeights.value = { a: 20, b: 22, topic: 40 }
    ctx.mindMapTopicActualWidth.value = 80

    const slice = useMindMapLayoutSlice(ctx)
    slice.armMindMapMeasureBatch(3)
    slice.setMindMapNodeDimensions('a', 40, 20)
    slice.setMindMapNodeDimensions('b', 50, 22)
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    slice.setMindMapTopicMeasured(80, 40)
    expect(scheduleMindMapRecalc).toHaveBeenCalledTimes(1)
  })

  it('does not flush on animation frames before mounts report', () => {
    const rafCallbacks: FrameRequestCallback[] = []
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn((cb: FrameRequestCallback) => {
        rafCallbacks.push(cb)
        return rafCallbacks.length
      })
    )
    vi.stubGlobal(
      'cancelAnimationFrame',
      vi.fn(() => undefined)
    )
    vi.useFakeTimers()

    const scheduleMindMapRecalc = vi.fn()
    const ctx = makeLayoutCtx(scheduleMindMapRecalc)
    const slice = useMindMapLayoutSlice(ctx)
    slice.armMindMapMeasureBatch(3)

    for (const cb of [...rafCallbacks]) {
      cb(0)
    }
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    expect(ctx.mindMapBulkLoading.value).toBe(true)

    slice.setMindMapNodeDimensions('a', 40, 20)
    slice.setMindMapNodeDimensions('b', 50, 22)
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    slice.setMindMapTopicMeasured(80, 40)
    expect(scheduleMindMapRecalc).toHaveBeenCalledTimes(1)
  })

  it('coalesces late mounts after arm into one recalc', () => {
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn(() => 1)
    )
    vi.stubGlobal(
      'cancelAnimationFrame',
      vi.fn(() => undefined)
    )
    vi.useFakeTimers()

    const scheduleMindMapRecalc = vi.fn()
    const ctx = makeLayoutCtx(scheduleMindMapRecalc)
    const slice = useMindMapLayoutSlice(ctx)
    slice.armMindMapMeasureBatch(3)

    vi.advanceTimersByTime(30)
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()

    slice.setMindMapNodeDimensions('a', 40, 20)
    vi.advanceTimersByTime(10)
    slice.setMindMapNodeDimensions('b', 50, 22)
    vi.advanceTimersByTime(10)
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    slice.setMindMapTopicMeasured(80, 40)
    expect(scheduleMindMapRecalc).toHaveBeenCalledTimes(1)
  })

  it('ignores repeat reports from the same node id during batch', () => {
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn(() => 1)
    )
    vi.stubGlobal(
      'cancelAnimationFrame',
      vi.fn(() => undefined)
    )
    vi.useFakeTimers()

    const scheduleMindMapRecalc = vi.fn()
    const ctx = makeLayoutCtx(scheduleMindMapRecalc)
    const slice = useMindMapLayoutSlice(ctx)
    slice.armMindMapMeasureBatch(2)
    slice.setMindMapNodeDimensions('a', 40, 20)
    slice.setMindMapNodeDimensions('a', 41, 21)
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    slice.setMindMapTopicMeasured(80, 40)
    expect(scheduleMindMapRecalc).toHaveBeenCalledTimes(1)
  })

  it('flushes on quiet period after partial unique reports', () => {
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn(() => 1)
    )
    vi.stubGlobal(
      'cancelAnimationFrame',
      vi.fn(() => undefined)
    )
    vi.useFakeTimers()

    const scheduleMindMapRecalc = vi.fn()
    const ctx = makeLayoutCtx(scheduleMindMapRecalc)
    const slice = useMindMapLayoutSlice(ctx)
    slice.armMindMapMeasureBatch(3)
    slice.setMindMapNodeDimensions('a', 40, 20)
    slice.setMindMapNodeDimensions('b', 50, 22)
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    vi.advanceTimersByTime(63)
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(scheduleMindMapRecalc).toHaveBeenCalledTimes(1)
    expect(ctx.mindMapBulkLoading.value).toBe(false)
  })

  it('flushes on safety timeout when measurements never arrive', () => {
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn(() => 1)
    )
    vi.stubGlobal(
      'cancelAnimationFrame',
      vi.fn(() => undefined)
    )
    vi.useFakeTimers()

    const scheduleMindMapRecalc = vi.fn()
    const ctx = makeLayoutCtx(scheduleMindMapRecalc)
    const slice = useMindMapLayoutSlice(ctx)
    slice.armMindMapMeasureBatch(3)

    vi.advanceTimersByTime(1499)
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(scheduleMindMapRecalc).toHaveBeenCalledTimes(1)
    expect(ctx.mindMapBulkLoading.value).toBe(false)
  })

  it('cancels arm safety on first report so overdue timer cannot beat quiet', () => {
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn(() => 1)
    )
    vi.stubGlobal(
      'cancelAnimationFrame',
      vi.fn(() => undefined)
    )
    vi.useFakeTimers()

    const scheduleMindMapRecalc = vi.fn()
    const ctx = makeLayoutCtx(scheduleMindMapRecalc)
    const slice = useMindMapLayoutSlice(ctx)
    slice.armMindMapMeasureBatch(3)

    // Nearly at arm safety — first report must replace it with progress safety.
    vi.advanceTimersByTime(1490)
    slice.setMindMapNodeDimensions('a', 40, 20)
    slice.setMindMapNodeDimensions('b', 50, 22)
    vi.advanceTimersByTime(10)
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    expect(ctx.mindMapBulkLoading.value).toBe(true)

    // Quiet (64ms from last unique report), not the original 1.5s arm safety.
    vi.advanceTimersByTime(54)
    expect(scheduleMindMapRecalc).toHaveBeenCalledTimes(1)
    expect(ctx.mindMapBulkLoading.value).toBe(false)
  })

  it('resets progress safety on each unique report so quiet still wins', () => {
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn(() => 1)
    )
    vi.stubGlobal(
      'cancelAnimationFrame',
      vi.fn(() => undefined)
    )
    vi.useFakeTimers()

    const scheduleMindMapRecalc = vi.fn()
    const ctx = makeLayoutCtx(scheduleMindMapRecalc)
    const slice = useMindMapLayoutSlice(ctx)
    // Enough pending that count0 never ends the batch during the trickle.
    slice.armMindMapMeasureBatch(20)

    // Unique reports every 50ms (< quiet 64ms) past the 750ms progress mark.
    // Without per-report progress reset, arm-from-first would flush at 750.
    for (let i = 0; i < 16; i += 1) {
      slice.setMindMapNodeDimensions(`n${i}`, 40 + i, 20)
      vi.advanceTimersByTime(50)
      expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    }
    vi.advanceTimersByTime(64)
    expect(scheduleMindMapRecalc).toHaveBeenCalledTimes(1)
  })
})

describe('mind-map orthogonal sibling map', () => {
  it('groups topic children by side and other edges by source', () => {
    const edges = [
      { id: 'e1', source: 'topic', target: 'branch-r-1-0' },
      { id: 'e2', source: 'topic', target: 'branch-r-1-1' },
      { id: 'e3', source: 'topic', target: 'branch-l-1-0' },
      { id: 'e4', source: 'branch-r-1-0', target: 'branch-r-2-0' },
      { id: 'e5', source: 'branch-r-1-0', target: 'branch-r-2-1' },
    ]
    const map = buildMindMapOrthogonalSiblingMap(edges)
    expect(map.get('topic:right')?.map((e) => e.id)).toEqual(['e1', 'e2'])
    expect(map.get('topic:left')?.map((e) => e.id)).toEqual(['e3'])
    expect(map.get('branch-r-1-0')?.map((e) => e.id)).toEqual(['e4', 'e5'])
    expect(mindMapOrthogonalSiblingGroupKey('topic', 'branch-l-1-0')).toBe('topic:left')
  })
})
