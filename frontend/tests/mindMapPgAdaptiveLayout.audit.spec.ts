/**
 * Live audit: load mind-map specs exported from Postgres, switch all five
 * 导图样式, and verify pairwise adaptive gap math + no overlaps.
 *
 * Fixtures: ../tmp_pg_mindmaps/*.json
 * Skips when fixtures are absent.
 */
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  DEFAULT_MINDMAP_BRANCH_GAP,
  MINDMAP_UNDERLINE_SIBLING_GAP,
} from '@/composables/diagrams/layoutConfig'
import {
  mindMapAdaptiveBranchGap,
  mindMapAdaptiveSiblingGap,
} from '@/config/mindMapAdaptiveGaps'
import { MIND_MAP_DIAGRAM_STYLES, type MindMapDiagramStyleId } from '@/config/mindMapDiagramStyles'
import { recalculateMindMapV2ColumnPositions } from '@/stores/diagram/mindMapLayout'
import {
  loadMindMapSpec,
  nodesAndConnectionsToMindMapSpec,
} from '@/stores/specLoader/mindMap'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import type { Connection, DiagramNode } from '@/types'
import { isMindMapL1, mindMapNodeSide } from '@/utils/mindMapLocation'
import type { NodeShape } from '@/utils/nodeShapeStyle'

const FIXTURE_DIR = resolve(__dirname, '../../tmp_pg_mindmaps')
const STYLES = MIND_MAP_DIAGRAM_STYLES.map((s) => s.id) as MindMapDiagramStyleId[]
const FIXTURE_FILES = ['xiaomi.json', 'switch.json', 'formal_new.json', 'iphone.json'] as const

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
  const raw = readFileSync(resolve(FIXTURE_DIR, name), 'utf8').trim()
  return JSON.parse(raw) as Record<string, unknown>
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
    leftBranches: (spec.leftBranches as unknown[]) || (spec.left as unknown[]) || undefined,
    rightBranches:
      (spec.rightBranches as unknown[]) || (spec.right as unknown[]) || undefined,
    _mindmap_diagram_style: style,
  })
}

function nodeHeight(n: DiagramNode): number {
  const h = n.data?.estimatedHeight
  return typeof h === 'number' && h > 0 ? h : 34
}

function nodeShapeOf(n: DiagramNode): NodeShape {
  return (n.style?.nodeShape as NodeShape | undefined) ?? 'rounded'
}

function sideSpan(nodes: DiagramNode[], side: 'l' | 'r'): number {
  const wanted = side === 'l' ? 'left' : 'right'
  let minY = Infinity
  let maxY = -Infinity
  for (const n of nodes) {
    if (!n.position || mindMapNodeSide(n.id, { nodes }) !== wanted) continue
    minY = Math.min(minY, n.position.y)
    maxY = Math.max(maxY, n.position.y + nodeHeight(n))
  }
  if (!Number.isFinite(minY)) return 0
  return maxY - minY
}

function totalSideSpan(nodes: DiagramNode[]): number {
  return sideSpan(nodes, 'r') + sideSpan(nodes, 'l')
}

function buildChildrenMap(connections: Connection[]): Map<string, string[]> {
  const childrenByParent = new Map<string, string[]>()
  for (const c of connections) {
    const list = childrenByParent.get(c.source) ?? []
    list.push(c.target)
    childrenByParent.set(c.source, list)
  }
  return childrenByParent
}

function subtreeBounds(
  rootId: string,
  byId: Map<string, DiagramNode>,
  childrenByParent: Map<string, string[]>
): { top: number; bottom: number } | null {
  const root = byId.get(rootId)
  if (!root?.position) return null
  let top = root.position.y
  let bottom = root.position.y + nodeHeight(root)
  const stack = [...(childrenByParent.get(rootId) ?? [])]
  while (stack.length) {
    const id = stack.pop()!
    const n = byId.get(id)
    if (!n?.position) continue
    top = Math.min(top, n.position.y)
    bottom = Math.max(bottom, n.position.y + nodeHeight(n))
    for (const kid of childrenByParent.get(id) ?? []) stack.push(kid)
  }
  return { top, bottom }
}

function firstLeafId(rootId: string, childrenByParent: Map<string, string[]>): string {
  let cur = rootId
  for (;;) {
    const kids = childrenByParent.get(cur)
    if (!kids?.length) return cur
    cur = kids[0]!
  }
}

function lastLeafId(rootId: string, childrenByParent: Map<string, string[]>): string {
  let cur = rootId
  for (;;) {
    const kids = childrenByParent.get(cur)
    if (!kids?.length) return cur
    cur = kids[kids.length - 1]!
  }
}

/**
 * Same-side sibling columns only:
 * - L2+ under a parent → adaptive sibling gap between consecutive subtree AABBs
 * - L1 under topic (left/right separately) → adaptive branch gap
 * Gap uses last-leaf / first-leaf shapes (matches layout packer).
 */
function assertSiblingGapMath(
  nodes: DiagramNode[],
  connections: Connection[],
  label: string
): { pairsChecked: number } {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const childrenByParent = buildChildrenMap(connections)

  const columns: { kids: string[]; mode: 'sibling' | 'branch'; name: string }[] = []
  const topicKids = childrenByParent.get('topic') ?? []
  columns.push({
    kids: topicKids.filter((id) => mindMapNodeSide(id, { nodes, connections }) === 'left'),
    mode: 'branch',
    name: 'L1-left',
  })
  columns.push({
    kids: topicKids.filter((id) => mindMapNodeSide(id, { nodes, connections }) === 'right'),
    mode: 'branch',
    name: 'L1-right',
  })
  for (const [parentId, kids] of childrenByParent) {
    if (parentId === 'topic' || kids.length < 2) continue
    columns.push({ kids: [...kids], mode: 'sibling', name: parentId })
  }

  let pairsChecked = 0
  for (const col of columns) {
    if (col.kids.length < 2) continue
    // Connection / list order is sibling SoT (matches layout packer).
    const ordered = col.kids
    for (let i = 1; i < ordered.length; i++) {
      const upperId = ordered[i - 1]!
      const lowerId = ordered[i]!
      const upperB = subtreeBounds(upperId, byId, childrenByParent)
      const lowerB = subtreeBounds(lowerId, byId, childrenByParent)
      if (!upperB || !lowerB) continue
      const gap = lowerB.top - upperB.bottom
      const upperLeaf = byId.get(lastLeafId(upperId, childrenByParent))!
      const lowerLeaf = byId.get(firstLeafId(lowerId, childrenByParent))!
      const expected =
        col.mode === 'branch'
          ? mindMapAdaptiveBranchGap(nodeShapeOf(upperLeaf), nodeShapeOf(lowerLeaf))
          : mindMapAdaptiveSiblingGap(nodeShapeOf(upperLeaf), nodeShapeOf(lowerLeaf))
      expect(
        gap,
        `${label}/${col.name}: ${upperId}→${lowerId} gap ${gap} vs ${expected} ` +
          `(${nodeShapeOf(upperLeaf)}/${nodeShapeOf(lowerLeaf)}, ${col.mode})`
      ).toBeCloseTo(expected, 0)
      expect(gap, `${label}/${col.name}: overlap ${upperId}/${lowerId}`).toBeGreaterThanOrEqual(
        -0.5
      )
      pairsChecked += 1
    }
  }
  return { pairsChecked }
}

function heightsFromNodes(nodes: DiagramNode[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const n of nodes) {
    const h = n.data?.estimatedHeight
    if (typeof h === 'number' && h > 0) out[n.id] = h
  }
  return out
}

const hasFixtures =
  existsSync(FIXTURE_DIR) && readdirSync(FIXTURE_DIR).some((f) => f.endsWith('.json'))

describe.runIf(hasFixtures)('PG mind-map adaptive layout audit', () => {
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

  for (const file of FIXTURE_FILES) {
    it(`${file}: all 5 styles — sibling gap math + underline tighter than formal`, () => {
      const path = resolve(FIXTURE_DIR, file)
      if (!existsSync(path)) return
      const spec = loadFixture(file)
      const spans: Partial<Record<MindMapDiagramStyleId, number>> = {}
      let totalPairs = 0

      for (const style of STYLES) {
        const loaded = loadStyledFromSpec(spec, style)
        expect(loaded.nodes.length, `${file}/${style} nodes`).toBeGreaterThan(1)
        const { pairsChecked } = assertSiblingGapMath(
          loaded.nodes,
          loaded.connections,
          `${file}/${style}`
        )
        totalPairs += pairsChecked
        spans[style] = totalSideSpan(loaded.nodes)
      }

      console.log(`[audit] ${file} side spans`, spans, `siblingPairs=${totalPairs}`)
      expect(totalPairs, `${file}: expected sibling pairs`).toBeGreaterThan(0)
      expect(spans.underline!).toBeLessThan(spans.formal!)
      // Box-heavy formal should not beat mixed/underline compactness.
      expect(spans.classic!).toBeLessThanOrEqual(spans.formal!)
      expect(spans.bubble!).toBeLessThanOrEqual(spans.formal!)
    })
  }

  it('xiaomi.json: y-correct from spacious pinned Y compacts underline fans', () => {
    const spec = loadFixture('xiaomi.json')
    const nodes = (spec.nodes as DiagramNode[]).map((n) => ({ ...n }))
    const connections = (spec.connections as Connection[]) ?? []
    expect(nodes.length).toBeGreaterThan(10)

    for (const n of nodes) {
      if (n.position && n.id !== 'topic') {
        n.position = { ...n.position, y: n.position.y * 1.35 }
      }
      n.style = { ...(n.style || {}), nodeShape: 'underline' }
    }

    const heights = heightsFromNodes(nodes)
    const beforeRight = sideSpan(nodes, 'r')

    const { nodes: laidOut } = recalculateMindMapV2ColumnPositions(
      nodes,
      null,
      {},
      heights,
      connections,
      new Set(),
      'underline'
    )

    const afterRight = sideSpan(laidOut, 'r')
    console.log('[audit] xiaomi compact', { beforeRight, afterRight })
    expect(afterRight).toBeLessThan(beforeRight)
    expect(afterRight).toBeLessThan(beforeRight * 0.95)

    assertSiblingGapMath(laidOut, connections, 'xiaomi/compact-underline')

    const l1 = laidOut
      .filter(
        (n) =>
          isMindMapL1(n.id, connections) && mindMapNodeSide(n.id, { nodes: laidOut }) === 'right'
      )
      .sort((a, b) => (a.position?.y ?? 0) - (b.position?.y ?? 0))[0]
    expect(l1).toBeDefined()
    const kids = laidOut
      .filter((n) => connections.some((c) => c.source === l1!.id && c.target === n.id))
      .sort((a, b) => (a.position?.y ?? 0) - (b.position?.y ?? 0))
    if (kids.length >= 2) {
      const gap =
        kids[1]!.position!.y - (kids[0]!.position!.y + (heights[kids[0]!.id] ?? 34))
      expect(gap).toBeGreaterThanOrEqual(MINDMAP_UNDERLINE_SIBLING_GAP - 1)
      expect(gap).toBeLessThan(DEFAULT_MINDMAP_BRANCH_GAP)
    }
  })
})
