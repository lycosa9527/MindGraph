import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'

import { useMindMapLayoutSlice } from '@/stores/diagram/mindMapLayout'
import type { DiagramContext } from '@/stores/diagram/types'
import { loadSpecForDiagramType } from '@/stores/specLoader'
import { loadMindMapSpec } from '@/stores/specLoader/mindMap'
import { useUIStore } from '@/stores/ui'
import {
  buildMindMapOrthogonalSiblingMap,
  mindMapOrthogonalSiblingGroupKey,
} from '@/utils/mindMapOrthogonalSiblings'

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

describe('mind-map measure batch settle', () => {
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
    const ctx = {
      type: ref('mindmap' as const),
      mindMapTopicActualWidth: ref<number | null>(null),
      mindMapNodeWidths: ref<Record<string, number>>({}),
      mindMapNodeHeights: ref<Record<string, number>>({}),
      mindMapPreserveIncomingY: ref(false),
      data: ref(null),
      scheduleMindMapRecalc,
    } as unknown as DiagramContext

    const slice = useMindMapLayoutSlice(ctx)
    slice.armMindMapMeasureBatch(3)
    slice.setMindMapNodeDimensions('a', 40, 20)
    slice.setMindMapNodeDimensions('b', 50, 22)
    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    slice.setMindMapTopicMeasured(80, 40)
    expect(scheduleMindMapRecalc).toHaveBeenCalledTimes(1)

    vi.useRealTimers()
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
