/**
 * Audit: shared wrap SoT vs old box-only wrap on a real PG mind map fixture.
 */
import { existsSync, readFileSync, readdirSync, writeFileSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import {
  MIND_MAP_GEOMETRY,
  mindMapBranchFontSize,
  mindMapHorizontalPadding,
} from '@/config/mindMapGeometry'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { buildMindMapVectorSnapshot } from '@/utils/diagramMindMapVectorModel'
import { buildMindMapVectorSvg } from '@/utils/diagramMindMapVectorSvg'
import { parseMindMapExportText, estimateTextWidth } from '@/utils/diagramMindMapVectorText'
import {
  resolveMindMapBranchTextMaxWidthPx,
  resolveMindMapExportWrapColumnPx,
  resolveMindMapTopicTextMaxWidthPx,
  wrapMindMapExportLabelLines,
  wrapMindMapTextLines,
} from '@/utils/mindMapTextWrap'

const FIXTURE_DIR = join(__dirname, 'fixtures/pg_mindmaps')
const OUT_DIR = join(FIXTURE_DIR, '_e2e_out')

function pickFixture() {
  if (!existsSync(FIXTURE_DIR)) return null
  const files = readdirSync(FIXTURE_DIR)
    .filter((f) => f.endsWith('.json') && !f.startsWith('_'))
    .sort()
  for (const name of files) {
    const data = JSON.parse(readFileSync(join(FIXTURE_DIR, name), 'utf8')) as {
      title?: string
      diagram_type?: string
      spec: {
        nodes?: Array<{
          id: string
          text?: string
          type: string
          position?: { x: number; y: number }
          style?: Record<string, unknown>
        }>
        connections?: unknown[]
        _mindmap_diagram_style?: string
        _node_styles?: Record<string, Record<string, unknown>>
      }
    }
    if ((data.spec.nodes?.length ?? 0) >= 5) return { name, data }
  }
  return null
}

const picked = pickFixture()

describe.runIf(Boolean(picked))('mindMapTextWrap audit (real PG fixture)', () => {
  it('uses host text maxWidth (not box-only) and keeps short labels single-line', () => {
    expect(picked).not.toBeNull()
    if (!picked) return

    const nodes = picked.data.spec.nodes ?? []
    const widths: Record<string, number> = {}
    const heights: Record<string, number> = {}
    for (const node of nodes) {
      const fontSize =
        Number(node.style?.fontSize) || (node.id === 'topic' ? 18 : mindMapBranchFontSize(node.id))
      const plain = parseMindMapExportText(String(node.text ?? ''))
        .map((s) => s.text)
        .join('')
      const textW = estimateTextWidth(plain.replace(/\*\*|__/g, ''), fontSize)
      // Approximate DOM-sized boxes (padding+border ~28) like live canvas estimates.
      widths[node.id] = Math.max(90, Math.ceil(textW + 28))
      heights[node.id] = node.id === 'topic' ? 40 : 34
    }

    const snapshot = buildMindMapVectorSnapshot({
      canvasMode: 'v2',
      outlineWireframe: false,
      store: {
        type: picked.data.diagram_type || 'mind_map',
        data: {
          type: 'mind_map',
          nodes: nodes.map((node) => ({
            id: node.id,
            text: node.text ?? '',
            type: node.type as 'topic' | 'branch' | 'child' | 'center',
            position: node.position,
            style: node.style as never,
          })),
          connections: (picked.data.spec.connections ?? []) as never,
          _mindmap_diagram_style: picked.data.spec._mindmap_diagram_style,
          _node_styles: picked.data.spec._node_styles as never,
        },
        mindMapNodeWidths: widths,
        mindMapNodeHeights: heights,
        nodeDimensions: {},
        mindMapTopicActualWidth: widths.topic ?? null,
      },
    })
    expect(snapshot).not.toBeNull()
    if (!snapshot) return

    const svg = buildMindMapVectorSvg(snapshot)
    const rows: Array<Record<string, unknown>> = []
    let shortSingleLineOk = 0
    let columnImproved = 0

    for (const node of snapshot.nodes) {
      const isTopic = node.id === 'topic' || node.type === 'topic' || node.type === 'center'
      const shape = resolveMindMapNodeShape(
        { id: node.id, type: node.type as 'topic' | 'branch', style: node.style },
        snapshot.diagramStyleId
      )
      const fontSize =
        node.style.fontSize ??
        (isTopic ? MIND_MAP_GEOMETRY.topicFontSize : mindMapBranchFontSize(node.id))
      const fontWeight =
        node.style.fontWeight ?? (isTopic || /\*\*|__/.test(node.text) ? 'bold' : 'normal')
      const plain = parseMindMapExportText(node.text)
        .map((s) => s.text)
        .join('')
      const padX = mindMapHorizontalPadding(shape)
      const border =
        shape === 'underline' ? 0 : (node.style.borderWidth ?? MIND_MAP_GEOMETRY.borderWidth)
      const boxInner = node.width - padX * 2 - border * 2
      const hostMax = isTopic
        ? resolveMindMapTopicTextMaxWidthPx()
        : resolveMindMapBranchTextMaxWidthPx(plain, fontSize, { fontWeight: String(fontWeight) })
      const sharedCol = resolveMindMapExportWrapColumnPx({
        role: isTopic ? 'topic' : 'branch',
        text: plain,
        fontSize,
        fontWeight: String(fontWeight),
        boxWidth: node.width,
        paddingX: padX,
        borderWidth: border,
      })
      const oldBoxOnlyCol = Math.max(8, boxInner)
      const lines = wrapMindMapExportLabelLines({
        role: isTopic ? 'topic' : 'branch',
        text: plain,
        fontSize,
        fontWeight: String(fontWeight),
        fontFamily: MIND_MAP_GEOMETRY.fontFamily,
        boxWidth: node.width,
        paddingX: padX,
        borderWidth: border,
      })
      const oldLines = wrapMindMapTextLines(plain, oldBoxOnlyCol, {
        fontSize,
        fontWeight: String(fontWeight),
        fontFamily: MIND_MAP_GEOMETRY.fontFamily,
      })

      if (hostMax > oldBoxOnlyCol + 0.5) columnImproved += 1
      // Settled canvas: label that fits host maxWidth stays one line.
      const fitsHost =
        !plain.includes('\n') &&
        estimateTextWidth(plain, fontSize, { isTopic: Boolean(isTopic || fontWeight === 'bold') }) <=
          hostMax
      if (fitsHost) {
        expect(lines.length).toBe(1)
        shortSingleLineOk += 1
      }

      rows.push({
        id: node.id,
        role: isTopic ? 'topic' : 'branch',
        boxW: node.width,
        boxInner: Number(boxInner.toFixed(1)),
        hostMax,
        sharedCol,
        oldBoxOnlyCol: Number(oldBoxOnlyCol.toFixed(1)),
        lines: lines.length,
        oldLines: oldLines.length,
        text: plain.slice(0, 28),
      })
    }

    mkdirSync(OUT_DIR, { recursive: true })
    const report = {
      fixture: picked.name,
      title: picked.data.title,
      nodes: rows.length,
      shortSingleLineOk,
      columnImproved,
      rows,
      svgHasText: svg.svg.includes('<text'),
      svgTspanCount: (svg.svg.match(/<tspan/g) || []).length,
    }
    writeFileSync(join(OUT_DIR, 'wrap-audit.json'), JSON.stringify(report, null, 2))

    expect(report.svgHasText).toBe(true)
    expect(shortSingleLineOk).toBeGreaterThan(0)
    // eslint-disable-next-line no-console
    console.log('[WRAP AUDIT]', {
      fixture: report.fixture,
      nodes: report.nodes,
      shortSingleLineOk,
      columnImproved,
      multiLineShared: rows.filter((r) => (r.lines as number) > 1).length,
      multiLineOldBoxOnly: rows.filter((r) => (r.oldLines as number) > 1).length,
    })
  })
})
