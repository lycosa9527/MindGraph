/**
 * Live layout positions after the leftover-edit + Kitty/voice add path.
 * Uses the real Pinia store and v2 column engine (no Vue Flow).
 * Optional PG suite reads tmp/pg_voice_add_layout/*.json (gitignored).
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { applyVoiceDiagramAddNodes } from '@/composables/editor/diagramVoiceMutations'
import { computeMindMapDisplayLayout } from '@/stores/diagram/mindMapDisplayLayout'
import { useDiagramStore } from '@/stores/diagram'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import type { DiagramNode } from '@/types'

function enableMindMapV2Canvas(): void {
  const flagsStore = useFeatureFlagsStore()
  flagsStore.flags = {
    external_base_url: '',
    feature_rag_chunk_test: false,
    feature_showcase: false,
    feature_knowledge_space: false,
    feature_library: false,
    feature_smart_response: false,
    feature_teacher_usage: false,
    feature_workshop_chat: false,
    feature_markets: false,
    feature_mindbot: false,
    feature_mindmate_export: false,
    feature_kitty_agent: false,
    feature_auth_pixel_battle: false,
    feature_test_server_banner: false,
    feature_thinking_coins: false,
    workshop_chat_preview_org_ids: [],
    feature_org_access: {},
  }
  useUIStore().mindMapCanvasMode = 'v2'
}

type Box = { id: string; x1: number; y1: number; x2: number; y2: number }

function nodeBox(
  node: DiagramNode,
  widths: Record<string, number>,
  heights: Record<string, number>
): Box {
  const width = widths[node.id] ?? (node.data?.estimatedWidth as number | undefined) ?? 80
  const height = heights[node.id] ?? (node.data?.estimatedHeight as number | undefined) ?? 34
  const x = node.position?.x ?? 0
  const y = node.position?.y ?? 0
  return { id: node.id, x1: x, y1: y, x2: x + width, y2: y + height }
}

function overlapArea(a: Box, b: Box): number {
  const ix = Math.min(a.x2, b.x2) - Math.max(a.x1, b.x1)
  const iy = Math.min(a.y2, b.y2) - Math.max(a.y1, b.y1)
  if (ix <= 0 || iy <= 0) return 0
  return ix * iy
}

function layoutStore(store: ReturnType<typeof useDiagramStore>) {
  const nodes = store.data?.nodes ?? []
  const connections = store.data?.connections ?? []
  return computeMindMapDisplayLayout(
    'v2',
    nodes,
    connections,
    store.mindMapTopicActualWidth,
    store.mindMapNodeWidths,
    store.mindMapNodeHeights
  )
}

function poisonTopicAsInlineEdit(store: ReturnType<typeof useDiagramStore>): void {
  store.setMindMapEditingNodeId('topic')
  store.mindMapTopicActualWidth = 800
  store.mindMapNodeWidths.topic = 800
  store.mindMapNodeHeights.topic = 220
}

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

describe('mind map voice/Kitty add layout positions', () => {
  beforeEach(() => {
    stubBrowser()
    setActivePinia(createPinia())
    enableMindMapV2Canvas()
  })

  it('voice add after leftover topic edit places the branch beside the topic', () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    poisonTopicAsInlineEdit(store)

    expect(applyVoiceDiagramAddNodes(store, [{ text: '照顾身体', side: 'right' }])).toBe(1)

    const laidOut = layoutStore(store)
    const topic = laidOut.nodes.find((node) => node.id === 'topic')
    const branch = laidOut.nodes.find((node) => node.text === '照顾身体')
    expect(topic?.position).toBeTruthy()
    expect(branch?.position).toBeTruthy()
    if (!topic || !branch) return

    expect(store.mindMapEditingNodeId).toBeNull()
    expect(store.mindMapTopicActualWidth).toBeNull()
    expect(store.mindMapNodeWidths.topic).not.toBe(800)

    const topicBox = nodeBox(topic, store.mindMapNodeWidths, store.mindMapNodeHeights)
    const branchBox = nodeBox(branch, store.mindMapNodeWidths, store.mindMapNodeHeights)
    expect(overlapArea(topicBox, branchBox), 'topic ∩ new branch').toBe(0)
    expect(branchBox.x1).toBeGreaterThanOrEqual(topicBox.x2)
    expect(topicBox.x2 - topicBox.x1).toBeLessThan(400)
  })

  it('local add after leftover topic edit also keeps topic and branch apart', () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    poisonTopicAsInlineEdit(store)

    expect(store.addMindMapBranch('right', '新分支')).toBe(true)

    const laidOut = layoutStore(store)
    const topic = laidOut.nodes.find((node) => node.id === 'topic')
    const branch = laidOut.nodes.find((node) => node.text === '新分支')
    expect(topic?.position && branch?.position).toBeTruthy()
    if (!topic || !branch) return

    const topicBox = nodeBox(topic, store.mindMapNodeWidths, store.mindMapNodeHeights)
    const branchBox = nodeBox(branch, store.mindMapNodeWidths, store.mindMapNodeHeights)
    expect(overlapArea(topicBox, branchBox), 'topic ∩ toolbar branch').toBe(0)
    expect(branchBox.x1).toBeGreaterThanOrEqual(topicBox.x2)
  })

  it('two voice adds do not stack the new branches on each other', () => {
    const store = useDiagramStore()
    store.loadDefaultTemplate('mindmap')
    poisonTopicAsInlineEdit(store)

    expect(applyVoiceDiagramAddNodes(store, [{ text: '照顾身体', side: 'right' }])).toBe(1)
    expect(applyVoiceDiagramAddNodes(store, [{ text: '小任务', side: 'right' }])).toBe(1)

    const laidOut = layoutStore(store)
    const first = laidOut.nodes.find((node) => node.text === '照顾身体')
    const second = laidOut.nodes.find((node) => node.text === '小任务')
    expect(first?.position && second?.position).toBeTruthy()
    if (!first || !second) return

    const a = nodeBox(first, store.mindMapNodeWidths, store.mindMapNodeHeights)
    const b = nodeBox(second, store.mindMapNodeWidths, store.mindMapNodeHeights)
    expect(overlapArea(a, b), 'branch ∩ branch').toBe(0)
  })
})

type PgFixture = {
  id: string
  title: string
  spec: Record<string, unknown>
}

const PG_DIR = resolve(__dirname, '../../tmp/pg_voice_add_layout')
const PROBE = '__kitty_add_probe__'

function loadPgFixtures(): PgFixture[] {
  if (!existsSync(PG_DIR)) return []
  return readdirSync(PG_DIR)
    .filter((name) => name.endsWith('.json'))
    .sort()
    .map((name) => JSON.parse(readFileSync(join(PG_DIR, name), 'utf8')) as PgFixture)
    .filter((row) => Array.isArray(row.spec?.nodes) && Array.isArray(row.spec?.connections))
}

function seedEstimateMaps(store: ReturnType<typeof useDiagramStore>): void {
  for (const node of store.data?.nodes ?? []) {
    const width = node.data?.estimatedWidth
    const height = node.data?.estimatedHeight
    if (typeof width === 'number') store.mindMapNodeWidths[node.id] = width
    if (typeof height === 'number') store.mindMapNodeHeights[node.id] = height
  }
}

function overlapsAgainst(probe: Box, others: Box[]): string[] {
  return others
    .filter((box) => box.id !== probe.id && overlapArea(probe, box) > 0.5)
    .map((box) => `${probe.id}∩${box.id}=${overlapArea(probe, box).toFixed(1)}`)
}

const pgFixtures = loadPgFixtures()

describe.runIf(pgFixtures.length > 0)('PG mind maps: leftover edit + voice add positions', () => {
  beforeEach(() => {
    stubBrowser()
    setActivePinia(createPinia())
    enableMindMapV2Canvas()
  })

  for (const fixture of pgFixtures) {
    it(`${fixture.title || fixture.id}: new branch does not overlap anyone`, () => {
      const store = useDiagramStore()
      expect(store.loadFromSpec(fixture.spec, 'mindmap')).toBe(true)
      expect(store.data?.nodes?.some((node) => node.id === 'topic')).toBe(true)

      seedEstimateMaps(store)
      poisonTopicAsInlineEdit(store)
      expect(applyVoiceDiagramAddNodes(store, [{ text: PROBE, side: 'right' }])).toBe(1)

      const laidOut = layoutStore(store)
      const topic = laidOut.nodes.find((node) => node.id === 'topic')
      const added = laidOut.nodes.find((node) => node.text === PROBE)
      expect(topic && added).toBeTruthy()
      if (!topic || !added) return

      expect(store.mindMapTopicActualWidth).toBeNull()
      expect(store.mindMapNodeWidths.topic).not.toBe(800)

      const boxes = laidOut.nodes
        .filter((node) => node.type !== 'boundary' && node.position)
        .map((node) => nodeBox(node, store.mindMapNodeWidths, store.mindMapNodeHeights))
      const addedBox = boxes.find((box) => box.id === added.id)
      const topicBox = boxes.find((box) => box.id === topic.id)
      expect(addedBox && topicBox).toBeTruthy()
      if (!addedBox || !topicBox) return

      expect(overlapsAgainst(addedBox, boxes), `${fixture.title}: new branch overlaps`).toEqual([])
      expect(addedBox.x1).toBeGreaterThanOrEqual(topicBox.x2)
    })
  }
})
