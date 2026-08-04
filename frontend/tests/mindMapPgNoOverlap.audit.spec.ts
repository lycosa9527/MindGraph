/**
 * Full AABB overlap audit on Postgres-exported mind-maps × all five 导图样式.
 * Skips when fixtures under tmp_pg_mindmaps/ are absent.
 */
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { MIND_MAP_DIAGRAM_STYLES, type MindMapDiagramStyleId } from '@/config/mindMapDiagramStyles'
import {
  loadMindMapSpec,
  nodesAndConnectionsToMindMapSpec,
} from '@/stores/specLoader/mindMap'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import type { Connection, DiagramNode } from '@/types'

const FIXTURE_DIR = resolve(__dirname, '../../tmp_pg_mindmaps')
const STYLES = MIND_MAP_DIAGRAM_STYLES.map((s) => s.id) as MindMapDiagramStyleId[]
const FILES = ['xiaomi.json', 'switch.json', 'formal_new.json', 'iphone.json'] as const

function enableMindMapV2Canvas(): void {
  const flagsStore = useFeatureFlagsStore()
  flagsStore.flags = {
    external_base_url: '',
    feature_rag_chunk_test: false,
    feature_course: false,
    feature_mate_learning: false,
    feature_template: false,
    feature_community: false,
    feature_showcase: false,
    feature_askonce: true,
    feature_debateverse: false,
    feature_knowledge_space: false,
    feature_mindmap_v2_canvas: true,
    feature_library: false,
    feature_gewe: false,
    feature_smart_response: false,
    feature_teacher_usage: false,
    feature_workshop_chat: false,
    feature_mindmate_collab: false,
    feature_markets: false,
    feature_mindbot: false,
    feature_mindmate_export: false,
    feature_kitty_agent: false,
    feature_auth_pixel_battle: false,
    feature_test_server_banner: false,
    feature_oauth_login: false,
    feature_thinking_coins: false,
    workshop_chat_preview_org_ids: [],
    feature_org_access: {},
  }
  useUIStore().mindMapCanvasMode = 'v2'
}

function loadFixture(name: string): Record<string, unknown> {
  return JSON.parse(readFileSync(resolve(FIXTURE_DIR, name), 'utf8').trim()) as Record<
    string,
    unknown
  >
}

function loadStyledFromSpec(spec: Record<string, unknown>, style: MindMapDiagramStyleId) {
  const nodes = spec.nodes as DiagramNode[] | undefined
  const connections = (spec.connections as Connection[] | undefined) ?? []
  if (nodes?.length) {
    const tree = nodesAndConnectionsToMindMapSpec(nodes, connections)
    return loadMindMapSpec({
      topic: tree.topic,
      leftBranches: tree.leftBranches,
      rightBranches: tree.rightBranches,
      preserveLeftRight: true,
      _mindmap_diagram_style: style,
    })
  }
  return loadMindMapSpec({
    topic: (spec.topic as string) || (spec.central_topic as string) || '',
    children: (spec.children as unknown[]) || [],
    _mindmap_diagram_style: style,
  })
}

function nodeHeight(n: DiagramNode): number {
  const v = n.data?.estimatedHeight
  return typeof v === 'number' && v > 0 ? v : 34
}

function nodeWidth(n: DiagramNode): number {
  const v = n.data?.estimatedWidth
  return typeof v === 'number' && v > 0 ? v : 80
}

type Box = { id: string; x1: number; y1: number; x2: number; y2: number }

function boxesOf(nodes: DiagramNode[]): Box[] {
  return nodes
    .filter((n) => n.position)
    .map((n) => ({
      id: n.id,
      x1: n.position!.x,
      y1: n.position!.y,
      x2: n.position!.x + nodeWidth(n),
      y2: n.position!.y + nodeHeight(n),
    }))
}

function overlapArea(a: Box, b: Box): number {
  const ix = Math.min(a.x2, b.x2) - Math.max(a.x1, b.x1)
  const iy = Math.min(a.y2, b.y2) - Math.max(a.y1, b.y1)
  if (ix <= 0 || iy <= 0) return 0
  return ix * iy
}

const hasFixtures =
  existsSync(FIXTURE_DIR) && readdirSync(FIXTURE_DIR).some((f) => f.endsWith('.json'))

describe.runIf(hasFixtures)('PG mind-map no AABB overlap', () => {
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
    enableMindMapV2Canvas()
  })

  for (const file of FILES) {
    it(`${file}: no node AABB overlaps across all 5 styles`, () => {
      const spec = loadFixture(file)
      const report: Record<string, { pairs: number; overlaps: number }> = {}

      for (const style of STYLES) {
        const { nodes } = loadStyledFromSpec(spec, style)
        const boxes = boxesOf(nodes)
        let overlaps = 0
        const hits: string[] = []
        for (let i = 0; i < boxes.length; i++) {
          for (let j = i + 1; j < boxes.length; j++) {
            const a = boxes[i]!
            const b = boxes[j]!
            const area = overlapArea(a, b)
            if (area > 0.5) {
              overlaps += 1
              if (hits.length < 6) hits.push(`${a.id}∩${b.id}=${area.toFixed(1)}`)
            }
          }
        }
        report[style] = {
          pairs: (boxes.length * (boxes.length - 1)) / 2,
          overlaps,
        }
        expect(overlaps, `${file}/${style}: ${hits.join('; ')}`).toBe(0)
      }

      console.log(`[overlap] ${file}`, report)
    })
  }
})
