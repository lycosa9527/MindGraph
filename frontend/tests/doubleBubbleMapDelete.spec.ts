/**
 * Double bubble delete must leave at least one similarity and one node on each difference side.
 */
import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'

const spec = {
  left: '苹果',
  right: '梨',
  similarities: ['都是水果', '都可生食'],
  leftDifferences: ['红色', '圆形'],
  rightDifferences: ['黄色', '梨形'],
}

function idsFor(
  store: ReturnType<typeof useDiagramStore>,
  role: 'similarity' | 'leftDiff' | 'rightDiff'
): string[] {
  return (store.data?.nodes ?? [])
    .filter((node) => readDoubleBubbleRole(node) === role)
    .map((node) => node.id)
}

describe('double bubble map delete keeps one similarity and one difference', () => {
  beforeEach(() => {
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
    setActivePinia(createPinia())
  })

  it('deletes extra similarities and refuses the last one', () => {
    const store = useDiagramStore()
    expect(store.loadFromSpec(spec, 'double_bubble_map', { emitLoaded: false })).toBe(true)
    const similarities = idsFor(store, 'similarity')
    expect(similarities).toHaveLength(2)

    const partial = store.removeDoubleBubbleMapNodes(similarities)
    expect(partial.deleted).toBe(1)
    expect(partial.withheldSimilarity).toBe(true)
    expect(idsFor(store, 'similarity')).toHaveLength(1)

    const last = store.removeDoubleBubbleMapNodes(idsFor(store, 'similarity'))
    expect(last.deleted).toBe(0)
    expect(last.withheldSimilarity).toBe(true)
    expect(idsFor(store, 'similarity')).toHaveLength(1)
  })

  it('keeps one node on each difference side', () => {
    const store = useDiagramStore()
    expect(store.loadFromSpec(spec, 'double_bubble_map', { emitLoaded: false })).toBe(true)
    const left = idsFor(store, 'leftDiff')
    const right = idsFor(store, 'rightDiff')
    expect(left).toHaveLength(2)
    expect(right).toHaveLength(2)

    const outcome = store.removeDoubleBubbleMapNodes([...left, ...right])
    expect(outcome.deleted).toBe(2)
    expect(outcome.withheldDifference).toBe(true)
    expect(outcome.withheldSimilarity).toBe(false)
    expect(idsFor(store, 'leftDiff')).toHaveLength(1)
    expect(idsFor(store, 'rightDiff')).toHaveLength(1)

    const blocked = store.removeDoubleBubbleMapNodes([
      ...idsFor(store, 'leftDiff'),
      ...idsFor(store, 'rightDiff'),
    ])
    expect(blocked.deleted).toBe(0)
    expect(blocked.withheldDifference).toBe(true)
    expect(idsFor(store, 'leftDiff')).toHaveLength(1)
    expect(idsFor(store, 'rightDiff')).toHaveLength(1)
  })

  it('still deletes a non-final node in each column', () => {
    const store = useDiagramStore()
    expect(store.loadFromSpec(spec, 'double_bubble_map', { emitLoaded: false })).toBe(true)
    const outcome = store.removeDoubleBubbleMapNodes([
      idsFor(store, 'similarity')[0],
      idsFor(store, 'leftDiff')[0],
      idsFor(store, 'rightDiff')[1],
    ])
    expect(outcome).toEqual({
      deleted: 3,
      withheldSimilarity: false,
      withheldDifference: false,
    })
    expect(idsFor(store, 'similarity')).toHaveLength(1)
    expect(idsFor(store, 'leftDiff')).toHaveLength(1)
    expect(idsFor(store, 'rightDiff')).toHaveLength(1)
  })

  it('recenters the right difference column after the other right nodes are deleted', () => {
    const store = useDiagramStore()
    expect(
      store.loadFromSpec(
        {
          left: '主题A',
          right: '主题B',
          similarities: ['相似点 1', '相似点 2'],
          leftDifferences: ['不同点A1', '不同点A2', '不同点A3'],
          rightDifferences: ['不同点B1', '不同点B2', '不同点B3'],
        },
        'double_bubble_map',
        { emitLoaded: false }
      )
    ).toBe(true)

    const removed = store.removeDoubleBubbleMapNodes(idsFor(store, 'rightDiff').slice(1))
    expect(removed.deleted).toBe(2)
    expect(idsFor(store, 'rightDiff')).toHaveLength(1)
    expect(idsFor(store, 'leftDiff')).toHaveLength(3)

    const topic = store.data?.nodes.find((node) => node.id === 'left-topic')
    const right = store.data?.nodes.find((node) => readDoubleBubbleRole(node) === 'rightDiff')
    const left = (store.data?.nodes ?? [])
      .filter((node) => readDoubleBubbleRole(node) === 'leftDiff')
      .sort((a, b) => a.position.y - b.position.y)
    if (!topic || !right || left.length !== 3) {
      throw new Error('expected topic, one right difference, and three left differences')
    }

    const topicCenter = topic.position.y + (topic.style?.size ?? 0) / 2
    const rightCenter = right.position.y + (right.style?.height ?? 0) / 2
    const topLeftCenter = left[0].position.y + (left[0].style?.height ?? 0) / 2
    expect(rightCenter).toBeCloseTo(topicCenter, 0)
    expect(Math.abs(rightCenter - topLeftCenter)).toBeGreaterThan(1)
  })

  it('keeps the surviving node radius after a larger sibling is deleted', () => {
    const store = useDiagramStore()
    expect(store.loadFromSpec(spec, 'double_bubble_map', { emitLoaded: false })).toBe(true)
    const similarities = (store.data?.nodes ?? []).filter(
      (node) => readDoubleBubbleRole(node) === 'similarity'
    )
    const larger = similarities[0]
    const smaller = similarities[1]
    if (!larger?.style || !smaller?.style) {
      throw new Error('expected two similarity nodes')
    }
    larger.style = { ...larger.style, size: 200 }
    smaller.style = { ...smaller.style, size: 80 }

    const outcome = store.removeDoubleBubbleMapNodes([larger.id])
    expect(outcome.deleted).toBe(1)
    const kept = (store.data?.nodes ?? []).find(
      (node) => readDoubleBubbleRole(node) === 'similarity'
    )
    expect(kept?.id).toBe(smaller.id)
    expect(kept?.style?.size ?? 0).toBeLessThan(120)
  })
})
