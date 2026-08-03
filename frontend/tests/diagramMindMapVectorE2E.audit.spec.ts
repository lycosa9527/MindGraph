/**
 * Production-readiness E2E audit: real PG mind map → vector SVG → PDF (+ DOCX PNG).
 * Writes artifacts under tests/fixtures/pg_mindmaps/_e2e_out/
 */
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

import { buildMindMapVectorSnapshot } from '@/utils/diagramMindMapVectorModel'
import { buildA4PdfFromMindMapVectors } from '@/utils/diagramMindMapVectorPdf'
import {
  __clearMindMapVectorPdfFontCacheForTests,
} from '@/utils/diagramMindMapVectorPdfFonts'
import { buildMindMapVectorSvg } from '@/utils/diagramMindMapVectorSvg'
import { estimateTextWidth } from '@/utils/diagramMindMapVectorText'

const FIXTURE_DIR = join(__dirname, 'fixtures/pg_mindmaps')
const OUT_DIR = join(FIXTURE_DIR, '_e2e_out')
const FONTS_DIR = join(__dirname, '../public/fonts')

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

function pickFixture(): { name: string; data: FixtureFile } | null {
  if (!existsSync(FIXTURE_DIR)) return null
  const files = readdirSync(FIXTURE_DIR)
    .filter((f) => f.endsWith('.json') && !f.startsWith('_'))
    .sort()
  for (const name of files) {
    const data = JSON.parse(readFileSync(join(FIXTURE_DIR, name), 'utf8')) as FixtureFile
    if ((data.spec.nodes?.length ?? 0) >= 5) {
      return { name, data }
    }
  }
  return null
}

function estimateSizes(nodes: NonNullable<FixtureFile['spec']['nodes']>) {
  const widths: Record<string, number> = {}
  const heights: Record<string, number> = {}
  for (const node of nodes) {
    const fontSize = Number(node.style?.fontSize) || (node.id === 'topic' ? 18 : 14)
    const text = String(node.text ?? '')
    const textW = estimateTextWidth(text.replace(/\*\*|__/g, ''), fontSize)
    widths[node.id] = Math.max(90, Math.ceil(textW + 28))
    heights[node.id] = node.id === 'topic' ? 40 : 34
  }
  return { widths, heights }
}

const picked = pickFixture()
const hasFonts =
  existsSync(join(FONTS_DIR, 'NotoSansSC-Regular.ttf')) &&
  existsSync(join(FONTS_DIR, 'NotoSansSC-Bold.ttf'))

describe.runIf(Boolean(picked) && hasFonts)('mind-map vector export E2E audit (real PG + fonts)', () => {
  beforeAll(() => {
    mkdirSync(OUT_DIR, { recursive: true })
    __clearMindMapVectorPdfFontCacheForTests()

    // jsdom lacks SVG getBBox — svg2pdf needs it for <text>. Approximate with font metrics.
    const proto = (globalThis as unknown as { SVGElement?: { prototype: object } }).SVGElement
      ?.prototype as { getBBox?: () => DOMRect } | undefined
    if (proto && typeof proto.getBBox !== 'function') {
      proto.getBBox = function getBBox(this: Element) {
        const text = (this.textContent || '').replace(/\s+/g, ' ')
        const fontSize = Number(this.getAttribute('font-size')) || 14
        const width = Math.max(1, estimateTextWidth(text, fontSize))
        const height = fontSize * 1.2
        return {
          x: 0,
          y: -fontSize,
          width,
          height,
          top: -fontSize,
          left: 0,
          right: width,
          bottom: -fontSize + height,
          toJSON: () => ({}),
        } as DOMRect
      }
    }

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        const name = url.includes('Bold')
          ? 'NotoSansSC-Bold.ttf'
          : url.includes('Regular')
            ? 'NotoSansSC-Regular.ttf'
            : null
        if (
          name &&
          (url.includes('/api/mindmap_export_fonts/') || url.includes('/fonts/'))
        ) {
          const bytes = readFileSync(join(FONTS_DIR, name))
          return new Response(bytes, {
            status: 200,
            headers: { 'Content-Type': 'font/ttf' },
          })
        }
        return new Response('not found', { status: 404 })
      })
    )
  })

  afterAll(() => {
    vi.unstubAllGlobals()
    __clearMindMapVectorPdfFontCacheForTests()
  })

  it('exports PDF with embedded TrueType fonts and reports size', async () => {
    expect(picked).not.toBeNull()
    if (!picked) return

    const nodes = picked.data.spec.nodes ?? []
    const { widths, heights } = estimateSizes(nodes)
    const snapshot = buildMindMapVectorSnapshot({
      canvasMode: 'v2',
      outlineWireframe: false,
      store: {
        type: picked.data.diagram_type || 'mind_map',
        data: {
          type: (picked.data.spec.type as 'mind_map') || 'mind_map',
          nodes: nodes.map((node) => ({
            id: node.id,
            text: node.text ?? '',
            type: node.type,
            position: node.position,
            style: node.style as never,
          })),
          connections: picked.data.spec.connections ?? [],
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

    const vector = buildMindMapVectorSvg(snapshot)
    writeFileSync(join(OUT_DIR, 'e2e.svg'), vector.svg, 'utf8')
    expect(vector.svg).toContain('<text')
    expect(vector.svg).toContain('<path')
    expect(vector.svg).toContain('Noto Sans SC')

    const started = Date.now()
    const pdf = await buildA4PdfFromMindMapVectors(
      [{ vector, headerCapture: null }],
      vector.width >= vector.height ? 'landscape' : 'portrait'
    )
    const elapsedMs = Date.now() - started
    const dataUri = pdf.output('datauristring')
    expect(dataUri.startsWith('data:application/pdf')).toBe(true)
    const b64 = dataUri.split(',')[1] ?? ''
    const pdfBuf = Buffer.from(b64, 'base64')
    writeFileSync(join(OUT_DIR, 'e2e.pdf'), pdfBuf)

    const kb = pdfBuf.length / 1024
    const report = {
      fixture: picked.name,
      title: picked.data.title,
      diagramId: picked.data.id,
      nodes: nodes.length,
      svgBytes: Buffer.byteLength(vector.svg, 'utf8'),
      pdfBytes: pdfBuf.length,
      pdfKB: Number(kb.toFixed(1)),
      pdfMB: Number((pdfBuf.length / (1024 * 1024)).toFixed(3)),
      buildMs: elapsedMs,
      fontSource: 'local public/fonts (same bytes as COS publish)',
      // Browser CSP forbids subset-font/wawoff2 (unsafe-eval).
      subset: false,
      magic: pdfBuf.subarray(0, 4).toString(),
    }
    writeFileSync(join(OUT_DIR, 'e2e-report.json'), JSON.stringify(report, null, 2))

    // Production gates
    expect(report.magic).toBe('%PDF')
    const pdfLatin = pdfBuf.toString('latin1')
    expect(pdfLatin.includes('FontFile2')).toBe(true)
    expect(pdfLatin.includes('CIDFont')).toBe(true)
    // TrueType must embed (not the broken ~3KB OTF path); jsPDF may compress.
    expect(pdfBuf.length).toBeGreaterThan(100_000)
    expect(pdfBuf.length).toBeLessThan(8 * 1024 * 1024)

    // eslint-disable-next-line no-console
    console.log('[E2E PDF]', report)
  }, 180_000)

  it('builds high-DPI DOCX diagram PNG from the same vector SVG', async () => {
    expect(picked).not.toBeNull()
    if (!picked) return
    const nodes = picked.data.spec.nodes ?? []
    const { widths, heights } = estimateSizes(nodes)
    const snapshot = buildMindMapVectorSnapshot({
      canvasMode: 'v2',
      outlineWireframe: false,
      store: {
        type: picked.data.diagram_type || 'mind_map',
        data: {
          type: (picked.data.spec.type as 'mind_map') || 'mind_map',
          nodes: nodes.map((node) => ({
            id: node.id,
            text: node.text ?? '',
            type: node.type,
            position: node.position,
            style: node.style as never,
          })),
          connections: picked.data.spec.connections ?? [],
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
    const vector = buildMindMapVectorSvg(snapshot)

    const sharp = (await import('sharp')).default
    const png = await sharp(Buffer.from(vector.svg), { density: 300 }).png().toBuffer()
    writeFileSync(join(OUT_DIR, 'e2e-docx-diagram.png'), png)
    expect(png.length).toBeGreaterThan(5_000)

    const { spawnSync } = await import('node:child_process')
    const repoRoot = join(__dirname, '../..')
    const outDocx = join(OUT_DIR, 'e2e.docx')
    const py = spawnSync(
      '/home/royw/miniconda3/envs/python313/bin/python',
      [
        '-c',
        `
from pathlib import Path
import sys
sys.path.insert(0, ${JSON.stringify(repoRoot)})
from services.diagram.worksheet_docx import WorksheetDocxSpec, WorksheetDocxLabels, build_worksheet_docx
png = Path(${JSON.stringify(join(OUT_DIR, 'e2e-docx-diagram.png'))}).read_bytes()
spec = WorksheetDocxSpec(
    title=${JSON.stringify(picked.data.title || 'e2e')},
    layout='landscape',
    show_topic=True,
    show_name=True,
    show_class=True,
    show_date=True,
    show_instruction=True,
    topic_text=${JSON.stringify(picked.data.title || 'e2e')},
    instruction_text='',
    diagram_offset_x=0.0,
    diagram_offset_y=0.0,
    diagram_scale=1.0,
    labels=WorksheetDocxLabels(
        name='姓名',
        class_name='班级',
        date='日期',
        instruction_prefix='说明：',
        default_instruction='请完成思维导图。',
    ),
)
out = Path(${JSON.stringify(outDocx)})
out.write_bytes(build_worksheet_docx(spec, png))
print(out.stat().st_size)
`,
      ],
      { encoding: 'utf8', cwd: repoRoot }
    )
    expect(py.status, py.stderr || py.stdout).toBe(0)
    const docxBytes = Number((py.stdout || '').trim())
    const report = {
      docxBytes,
      docxKB: Number((docxBytes / 1024).toFixed(1)),
      pngBytes: png.length,
      pngKB: Number((png.length / 1024).toFixed(1)),
    }
    writeFileSync(join(OUT_DIR, 'e2e-docx-report.json'), JSON.stringify(report, null, 2))
    expect(docxBytes).toBeGreaterThan(10_000)
    // eslint-disable-next-line no-console
    console.log('[E2E DOCX]', report)
  }, 120_000)
})
