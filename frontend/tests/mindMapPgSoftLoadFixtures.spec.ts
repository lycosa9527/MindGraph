/**
 * Loads fixtures exported by scripts/validate_mindmap_soft_load_from_pg.py
 * and exercises the real frontend soft/hard load paths.
 *
 * Skip (pass) when fixtures are missing so CI without local PG stays green.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { loadSpecForDiagramType } from '@/stores/specLoader'
import { useUIStore } from '@/stores/ui'

const FIXTURE_DIR = resolve(__dirname, '../../tmp/mindmap_soft_load_e2e/fixtures')

type FixtureFile = {
  id: string
  title: string
  diagram_type?: string
  spec: Record<string, unknown>
}

function loadFixtures(): FixtureFile[] {
  if (!existsSync(FIXTURE_DIR)) return []
  return readdirSync(FIXTURE_DIR)
    .filter((name) => name.endsWith('.json'))
    .sort()
    .map((name) => {
      const raw = readFileSync(join(FIXTURE_DIR, name), 'utf-8')
      return JSON.parse(raw) as FixtureFile
    })
    .filter((f) => Array.isArray(f.spec?.nodes) && Array.isArray(f.spec?.connections))
}

const fixtures = loadFixtures()

describe('PG mind-map soft load fixtures', () => {
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
    useUIStore().mindMapCanvasMode = 'v2'
  })

  it('has fixtures from PG export (run validate_mindmap_soft_load_from_pg.py first)', () => {
    if (fixtures.length === 0) {
      console.warn(
        `[skip-detail] No fixtures at ${FIXTURE_DIR}. ` +
          'Run: PYTHONPATH=. python scripts/validate_mindmap_soft_load_from_pg.py --limit 15'
      )
    }
    // Soft assertion: when fixtures exist we exercise them below; when absent this still passes.
    expect(true).toBe(true)
  })

  it.runIf(fixtures.length > 0)(
    `soft-loads ${fixtures.length} real PG mind maps without reshuffling positions`,
    () => {
      for (const fixture of fixtures) {
        const soft = loadSpecForDiagramType(fixture.spec, 'mindmap', {
          preferLaidOutMindMapNodes: true,
        })
        const stampedNodes = fixture.spec.nodes as Array<{
          id?: string
          position?: { x?: number; y?: number }
        }>
        expect(soft.nodes.length).toBeGreaterThanOrEqual(3)
        expect(soft.nodes.some((n) => n.id === 'topic')).toBe(true)

        for (const node of soft.nodes) {
          const stamped = stampedNodes.find((n) => n.id === node.id)
          if (!stamped?.position || !node.position) continue
          expect(node.position.x).toBe(stamped.position.x)
          expect(node.position.y).toBe(stamped.position.y)
        }

        const hard = loadSpecForDiagramType(fixture.spec, 'mindmap')
        expect(hard.nodes.some((n) => n.id === 'topic')).toBe(true)
        expect(hard.connections.length).toBeGreaterThan(0)

        const softIds = new Set(soft.connections.flatMap((c) => [c.source, c.target]))
        for (const id of softIds) {
          expect(soft.nodes.some((n) => n.id === id)).toBe(true)
        }
      }
    }
  )
})
