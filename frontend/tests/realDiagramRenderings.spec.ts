/**
 * Real saved diagrams through the library load path, compared with a baseline.
 *
 * Fixtures: tmp/real_diagrams/fixtures/*.json from
 * scripts/render_check/export_real_diagrams.py (gitignored, real labels).
 * The suite is skipped when there are no fixtures.
 *
 * For every fixture it records the nodes Vue Flow receives on first paint
 * (position + layout box) and checks that every value is finite. With a
 * baseline in tmp/real_diagrams/baseline-jsdom it also fails when a box moves
 * or resizes by more than 0.5px, or when overlaps between mind-map boxes grow.
 *
 * MG_RENDER_BASELINE=write records the baseline instead of comparing.
 * MG_RENDER_FIXTURE_DIR / MG_RENDER_BASELINE_DIR override the folders, so the
 * same file can record a baseline from a worktree of the last commit.
 */
import { createPinia, setActivePinia } from 'pinia'

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import { useUIStore } from '@/stores/ui'
import type { DiagramType } from '@/types'
import { mindMapLibraryLoadOptions } from '@/utils/mindMapLibraryLoadOptions'

type Fixture = {
  name: string
  diagram_type: string
  spec: Record<string, unknown>
}

/** `key` is type + label + occurrence: thinking maps mint fresh ids on every load. */
type NodeRow = { key: string; type: string; x: number; y: number; w: number; h: number }

type Snapshot = { nodes: NodeRow[]; overlaps: number }

const ROOT = resolve(__dirname, '../..')
const FIXTURE_DIR = process.env.MG_RENDER_FIXTURE_DIR ?? join(ROOT, 'tmp/real_diagrams/fixtures')
const BASELINE_DIR =
  process.env.MG_RENDER_BASELINE_DIR ?? join(ROOT, 'tmp/real_diagrams/baseline-jsdom')
const WRITE_BASELINE = process.env.MG_RENDER_BASELINE === 'write'
const TOLERANCE_PX = 0.5
const MIND_MAP_TYPES = new Set(['mindmap', 'mind_map'])

function loadFixtures(): Fixture[] {
  if (!existsSync(FIXTURE_DIR)) return []
  return readdirSync(FIXTURE_DIR)
    .filter((name) => name.endsWith('.json'))
    .sort()
    .map((name) => JSON.parse(readFileSync(join(FIXTURE_DIR, name), 'utf8')) as Fixture)
}

function finiteOr(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function round(value: number): number {
  return Math.round(value * 10) / 10
}

function snapshotStore(store: ReturnType<typeof useDiagramStore>): Snapshot {
  const dims = store.nodeDimensions as Record<string, { width: number; height: number }>
  const seen = new Map<string, number>()
  const nodes = store.vueFlowNodes.map((node): NodeRow => {
    const data = (node.data ?? {}) as Record<string, unknown>
    const stored = dims[node.id]
    const label = `${String(node.type ?? '')}:${String(data.label ?? '').slice(0, 40)}`
    const occurrence = seen.get(label) ?? 0
    seen.set(label, occurrence + 1)
    return {
      key: `${label}#${occurrence}`,
      type: String(node.type ?? ''),
      x: round(node.position.x),
      y: round(node.position.y),
      w: round(finiteOr(data.estimatedWidth, stored?.width ?? Number.NaN)),
      h: round(finiteOr(data.estimatedHeight, stored?.height ?? Number.NaN)),
    }
  })
  return { nodes, overlaps: countOverlaps(nodes) }
}

function countOverlaps(nodes: readonly NodeRow[]): number {
  const boxes = nodes.filter(
    (node) => node.type !== 'boundary' && Number.isFinite(node.w) && Number.isFinite(node.h)
  )
  let count = 0
  for (let i = 0; i < boxes.length; i += 1) {
    for (let j = i + 1; j < boxes.length; j += 1) {
      const a = boxes[i]
      const b = boxes[j]
      const ix = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)
      const iy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y)
      if (ix > 1 && iy > 1) count += 1
    }
  }
  return count
}

function describeDrift(before: Snapshot, after: Snapshot): string[] {
  const previous = new Map(before.nodes.map((node) => [node.key, node] as const))
  const drift: string[] = []
  for (const node of after.nodes) {
    const old = previous.get(node.key)
    if (!old) {
      drift.push(`${node.key}: new node`)
      continue
    }
    for (const key of ['x', 'y', 'w', 'h'] as const) {
      const a = old[key]
      const b = node[key]
      const both = Number.isFinite(a) && Number.isFinite(b)
      if ((both && Math.abs(a - b) > TOLERANCE_PX) || Number.isFinite(a) !== Number.isFinite(b)) {
        drift.push(`${node.key}.${key}: ${a} -> ${b}`)
      }
    }
  }
  const keys = new Set(after.nodes.map((node) => node.key))
  for (const node of before.nodes) if (!keys.has(node.key)) drift.push(`${node.key}: missing`)
  return drift
}

const fixtures = loadFixtures()

describe.runIf(fixtures.length > 0)('real diagrams: first-paint layout', () => {
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
    useUIStore().mindMapCanvasMode = 'v2'
  })

  for (const fixture of fixtures) {
    it(fixture.name, () => {
      const store = useDiagramStore()
      const type = fixture.diagram_type as DiagramType
      const loaded = store.loadFromSpec(
        fixture.spec,
        type,
        mindMapLibraryLoadOptions(type, fixture.spec)
      )
      expect(loaded, `${fixture.name} loads`).toBe(true)
      const snapshot = snapshotStore(store)
      const savedEmpty = Array.isArray(fixture.spec.nodes) && fixture.spec.nodes.length === 0
      if (!savedEmpty) {
        expect(snapshot.nodes.length, `${fixture.name} has nodes`).toBeGreaterThan(0)
      }
      const notFinite = snapshot.nodes.filter(
        (node) => !Number.isFinite(node.x) || !Number.isFinite(node.y)
      )
      expect(
        notFinite.map((node) => node.key),
        `${fixture.name} positions`
      ).toEqual([])

      const baselineFile = join(BASELINE_DIR, `${fixture.name}.json`)
      if (WRITE_BASELINE) {
        mkdirSync(BASELINE_DIR, { recursive: true })
        writeFileSync(baselineFile, JSON.stringify(snapshot))
        return
      }
      if (!existsSync(baselineFile)) return
      const baseline = JSON.parse(readFileSync(baselineFile, 'utf8')) as Snapshot
      expect(describeDrift(baseline, snapshot), `${fixture.name} drift`).toEqual([])
      if (MIND_MAP_TYPES.has(fixture.diagram_type)) {
        expect(snapshot.overlaps, `${fixture.name} overlaps`).toBeLessThanOrEqual(baseline.overlaps)
      }
    })
  }
})
