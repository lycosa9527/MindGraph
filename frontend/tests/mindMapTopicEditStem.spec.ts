/**
 * Topic text edits update the layout estimate only. The right-hand T follows
 * the painted width reported when editing ends.
 */
import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { DEFAULT_MINDMAP_RANK_SEPARATION } from '@/composables/diagrams/layoutConfig'
import { useDiagramStore } from '@/stores/diagram'
import { computeMindMapDisplayLayout } from '@/stores/diagram/mindMapDisplayLayout'
import { mindMapNodeSide } from '@/utils/mindMapLocation'

function stubBrowser(): void {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({
      matches: false,
      media: '',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
  )
}

describe('mind map topic edit stem', () => {
  beforeEach(() => {
    stubBrowser()
    setActivePinia(createPinia())
  })

  function loadPoisonedTopic(): { rightId: string; staleWidth: number } {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    const nodes = store.data?.nodes ?? []
    const connections = store.data?.connections ?? []
    const topic = nodes.find((node) => node.id === 'topic')
    if (!topic?.data) {
      throw new Error('expected a topic node')
    }
    const staleWidth = 480
    topic.data.estimatedWidth = staleWidth
    store.mindMapTopicActualWidth = staleWidth
    const rightId = connections.find(
      (connection) =>
        connection.source === 'topic' &&
        mindMapNodeSide(connection.target, { nodes, connections }) === 'right'
    )?.target
    if (!rightId) {
      throw new Error('expected a right-hand branch')
    }
    return { rightId, staleWidth }
  }

  it('keeps the painted width when the label estimate changes', () => {
    const store = useDiagramStore()
    const { staleWidth } = loadPoisonedTopic()

    expect(store.updateNode('topic', { text: '1' })).toBe(true)

    const estimate = store.data?.nodes.find((node) => node.id === 'topic')?.data?.estimatedWidth
    expect(estimate).toBeTypeOf('number')
    expect(estimate).toBeLessThan(200)
    expect(store.mindMapTopicActualWidth).toBe(staleWidth)
  })

  it('places the right-hand T on the painted edge once that width is measured', () => {
    const store = useDiagramStore()
    const { rightId, staleWidth } = loadPoisonedTopic()
    expect(store.updateNode('topic', { text: '1' })).toBe(true)

    const estimate = store.data?.nodes.find((node) => node.id === 'topic')?.data
      ?.estimatedWidth as number
    const painted = estimate + 6
    store.setMindMapTopicMeasured(painted, 40)

    const laidOut = computeMindMapDisplayLayout(
      'v2',
      store.data?.nodes ?? [],
      store.data?.connections ?? [],
      store.mindMapTopicActualWidth,
      store.mindMapNodeWidths,
      store.mindMapNodeHeights
    )
    const laidTopic = laidOut.nodes.find((node) => node.id === 'topic')
    const laidRight = laidOut.nodes.find((node) => node.id === rightId)
    expect(laidTopic?.position).toBeTruthy()
    expect(laidRight?.position).toBeTruthy()
    if (!laidTopic?.position || !laidRight?.position) return

    expect(store.mindMapTopicActualWidth).toBe(painted)
    expect(laidRight.position.x).toBeCloseTo(
      laidTopic.position.x + painted + DEFAULT_MINDMAP_RANK_SEPARATION,
      0
    )
    expect(laidRight.position.x).toBeLessThan(laidTopic.position.x + staleWidth)
  })
})
