/**
 * Verifies vector export against real PostgreSQL mind-map fixtures
 * (written by frontend/scripts/_tmp_fetch_pg_mindmaps.py).
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import { beforeAll, describe, expect, it } from 'vitest'

import { buildMindMapVectorSnapshot } from '@/utils/diagramMindMapVectorModel'
import { buildMindMapVectorSvg } from '@/utils/diagramMindMapVectorSvg'
import { estimateTextWidth } from '@/utils/diagramMindMapVectorText'

const FIXTURE_DIR = join(__dirname, 'fixtures/pg_mindmaps')
const OUT_DIR = join(__dirname, 'fixtures/pg_mindmaps/_out')

type FixtureFile = {
  id: string
  title: string
  diagram_type: string
  spec: {
    type?: string
    nodes?: Array<{
      id: string
      text?: string
      type: 'topic' | 'branch' | 'child' | 'center'
      position?: { x: number; y: number }
      style?: Record<string, unknown>
    }>
    connections?: Array<{ id: string; source: string; target: string }>
    _mindmap_diagram_style?: string
    _node_styles?: Record<string, Record<string, unknown>>
  }
}

function listFixtures(): string[] {
  if (!existsSync(FIXTURE_DIR)) return []
  return readdirSync(FIXTURE_DIR).filter(
    (name) => name.endsWith('.json') && !name.startsWith('_')
  )
}

function estimateSizes(fixture: FixtureFile): {
  widths: Record<string, number>
  heights: Record<string, number>
} {
  const widths: Record<string, number> = {}
  const heights: Record<string, number> = {}
  for (const node of fixture.spec.nodes ?? []) {
    const fontSize = Number(node.style?.fontSize) || (node.id === 'topic' ? 18 : 14)
    const text = String(node.text ?? '')
    const textW = estimateTextWidth(text.replace(/\*\*|__/g, ''), fontSize)
    widths[node.id] = Math.max(90, Math.ceil(textW + 28))
    heights[node.id] = node.id === 'topic' ? 40 : 34
  }
  return { widths, heights }
}

const files = listFixtures()

describe.runIf(files.length > 0)('mind-map vector export from PG fixtures', () => {
  beforeAll(() => {
    mkdirSync(OUT_DIR, { recursive: true })
  })

  it.each(files)('builds vector SVG for %s', async (fileName) => {
    const fixture = JSON.parse(
      readFileSync(join(FIXTURE_DIR, fileName), 'utf8')
    ) as FixtureFile

    const nodes = fixture.spec.nodes ?? []
    if (nodes.length === 0) {
      // Hierarchical-only specs (no flat nodes) are out of scope for this check.
      expect(nodes.length).toBe(0)
      return
    }

    const { widths, heights } = estimateSizes(fixture)
    const snapshot = buildMindMapVectorSnapshot({
      canvasMode: 'v2',
      outlineWireframe: false,
      store: {
        type: fixture.diagram_type || fixture.spec.type || 'mind_map',
        data: {
          type: (fixture.spec.type as 'mind_map') || 'mind_map',
          nodes: nodes.map((node) => ({
            id: node.id,
            text: node.text ?? '',
            type: node.type,
            position: node.position,
            style: node.style as never,
          })),
          connections: fixture.spec.connections ?? [],
          _mindmap_diagram_style: fixture.spec._mindmap_diagram_style,
          _node_styles: fixture.spec._node_styles as never,
        },
        mindMapNodeWidths: widths,
        mindMapNodeHeights: heights,
        nodeDimensions: {},
        mindMapTopicActualWidth: widths.topic ?? null,
      },
    })

    expect(snapshot).not.toBeNull()
    if (!snapshot) return

    const vector = buildMindMapVectorSvg(snapshot)
    expect(vector.svg).toContain('<svg')
    expect(vector.svg).toContain('<text')
    expect(vector.svg).toContain('<path')
    expect(vector.svg).toContain('Noto Sans SC')

    const sampleText = String(nodes[0]?.text ?? '')
    if (sampleText) {
      const token = sampleText.replace(/\*\*|__/g, '').slice(0, 2)
      if (token) expect(vector.svg).toContain(token)
    }

    const svgPath = join(OUT_DIR, `${fileName.replace(/\.json$/, '')}.svg`)
    writeFileSync(svgPath, vector.svg, 'utf8')
    expect(existsSync(svgPath)).toBe(true)
  })
})
