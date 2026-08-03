/**
 * End-to-end audit: real PG mind map → vector SVG → PDF (subset fonts) + DOCX PNG.
 *
 * Usage (frontend/):
 *   node scripts/audit-mindmap-vector-export.mjs
 *
 * Prefers fixture JSON under tests/fixtures/pg_mindmaps/; else prints how to fetch.
 */
import { createRequire } from 'node:module'
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  writeFileSync,
  statSync,
} from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'

const require = createRequire(import.meta.url)
const __dirname = dirname(fileURLToPath(import.meta.url))
const frontendRoot = join(__dirname, '..')
const repoRoot = join(frontendRoot, '..')
const outDir = join(frontendRoot, 'tests/fixtures/pg_mindmaps/_e2e_out')
const fontsDir = join(frontendRoot, 'public/fonts')
const fixtureDir = join(frontendRoot, 'tests/fixtures/pg_mindmaps')

function setupDom() {
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
    url: 'http://localhost:9527/',
    pretendToBeVisual: true,
  })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.DOMParser = dom.window.DOMParser
  globalThis.XMLSerializer = dom.window.XMLSerializer
  globalThis.btoa = (s) => Buffer.from(s, 'binary').toString('base64')
  globalThis.atob = (s) => Buffer.from(s, 'base64').toString('binary')
  globalThis.SVGSVGElement = dom.window.SVGSVGElement
  globalThis.Element = dom.window.Element
  globalThis.Node = dom.window.Node
  globalThis.HTMLElement = dom.window.HTMLElement
  globalThis.Image = dom.window.Image
  if (!globalThis.Buffer) globalThis.Buffer = Buffer
}

function installFontFetchMock() {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (input, init) => {
    const url = String(input)
    const name = url.includes('NotoSansCJKsc-Bold')
      ? 'NotoSansCJKsc-Bold.otf'
      : url.includes('NotoSansCJKsc-Regular')
        ? 'NotoSansCJKsc-Regular.otf'
        : null
    if (
      name &&
      (url.includes('/api/mindmap_export_fonts/') || url.includes('/fonts/'))
    ) {
      const path = join(fontsDir, name)
      if (!existsSync(path)) {
        return new Response('missing', { status: 404 })
      }
      const bytes = readFileSync(path)
      return new Response(bytes, {
        status: 200,
        headers: { 'Content-Type': 'font/otf' },
      })
    }
    if (typeof originalFetch === 'function') {
      return originalFetch(input, init)
    }
    return new Response('not found', { status: 404 })
  }
}

function pickFixture() {
  if (!existsSync(fixtureDir)) return null
  const files = readdirSync(fixtureDir)
    .filter((f) => f.endsWith('.json') && !f.startsWith('_'))
    .sort()
  for (const name of files) {
    const full = join(fixtureDir, name)
    const data = JSON.parse(readFileSync(full, 'utf8'))
    const nodes = data?.spec?.nodes ?? []
    if (nodes.length >= 5) {
      return { name, data }
    }
  }
  return null
}

function estimateSizes(nodes) {
  const widths = {}
  const heights = {}
  for (const node of nodes) {
    const text = String(node.text ?? '')
    const isTopic = node.id === 'topic'
    const fontSize = Number(node.style?.fontSize) || (isTopic ? 18 : 14)
    let w = 0
    for (const ch of text.replace(/\*\*|__/g, '')) {
      w += /[\u3400-\u9FFF]/.test(ch) ? fontSize : fontSize * 0.55
    }
    widths[node.id] = Math.max(90, Math.ceil(w + 28))
    heights[node.id] = isTopic ? 40 : 34
  }
  return { widths, heights }
}

async function loadTs(specifierFromSrc) {
  // Resolve via Vite-less relative import from compiled path using tsx/vite-node if present.
  // Prefer dynamic import through vitest's vite pipeline by spawning — here we use
  // relative file URLs under src with Node experimental TypeScript if available.
  const abs = join(frontendRoot, 'src', specifierFromSrc)
  return import(pathToFileURL(abs).href)
}

async function main() {
  mkdirSync(outDir, { recursive: true })
  const regular = join(fontsDir, 'NotoSansCJKsc-Regular.otf')
  const bold = join(fontsDir, 'NotoSansCJKsc-Bold.otf')
  const audit = {
    ok: false,
    checks: [],
    fixture: null,
    pdf: null,
    docxPng: null,
    errors: [],
  }

  function check(name, pass, detail = '') {
    audit.checks.push({ name, pass: Boolean(pass), detail })
    if (!pass) audit.errors.push(`${name}: ${detail || 'failed'}`)
  }

  check('font_regular_local', existsSync(regular), regular)
  check('font_bold_local', existsSync(bold), bold)

  const fixture = pickFixture()
  if (!fixture) {
    check(
      'pg_fixture',
      false,
      'Run: python frontend/scripts/fetch_pg_mindmaps_for_vector_export.py'
    )
    writeFileSync(join(outDir, 'audit.json'), JSON.stringify(audit, null, 2))
    console.log(JSON.stringify(audit, null, 2))
    process.exit(2)
  }
  audit.fixture = {
    file: fixture.name,
    title: fixture.data.title,
    id: fixture.data.id,
    nodes: fixture.data.spec.nodes.length,
  }
  check('pg_fixture', true, `${fixture.name} (${fixture.data.spec.nodes.length} nodes)`)

  setupDom()
  installFontFetchMock()

  // Use vitest/vite to transform TS imports — spawn a small worker via npx vite-node if available
  let viteNode
  try {
    viteNode = join(frontendRoot, 'node_modules/vite-node/vite-node.mjs')
    if (!existsSync(viteNode)) {
      // fallback: register tsx
      await import('tsx/esm/api').then((api) => api.register())
    }
  } catch {
    /* try direct import */
  }

  const { buildMindMapVectorSnapshot } = await import(
    pathToFileURL(join(frontendRoot, 'src/utils/diagramMindMapVectorModel.ts')).href
  ).catch(async () => {
    // tsx register path
    const { register } = await import('tsx/esm/api')
    register()
    return import(
      pathToFileURL(join(frontendRoot, 'src/utils/diagramMindMapVectorModel.ts')).href
    )
  })

  const { buildMindMapVectorSvg } = await import(
    pathToFileURL(join(frontendRoot, 'src/utils/diagramMindMapVectorSvg.ts')).href
  )
  const { buildA4PdfFromMindMapVectors } = await import(
    pathToFileURL(join(frontendRoot, 'src/utils/diagramMindMapVectorPdf.ts')).href
  )
  const { __clearMindMapVectorPdfFontCacheForTests } = await import(
    pathToFileURL(join(frontendRoot, 'src/utils/diagramMindMapVectorPdfFonts.ts')).href
  )

  __clearMindMapVectorPdfFontCacheForTests()

  const nodes = fixture.data.spec.nodes
  const { widths, heights } = estimateSizes(nodes)
  const snapshot = buildMindMapVectorSnapshot({
    canvasMode: 'v2',
    outlineWireframe: false,
    store: {
      type: fixture.data.diagram_type || 'mind_map',
      data: {
        type: fixture.data.spec.type || 'mind_map',
        nodes,
        connections: fixture.data.spec.connections ?? [],
        _mindmap_diagram_style: fixture.data.spec._mindmap_diagram_style,
        _node_styles: fixture.data.spec._node_styles,
      },
      mindMapNodeWidths: widths,
      mindMapNodeHeights: heights,
      nodeDimensions: {},
      mindMapTopicActualWidth: widths.topic ?? null,
    },
  })
  check('vector_snapshot', Boolean(snapshot), snapshot ? `${snapshot.nodes.length} draw nodes` : '')

  const vector = buildMindMapVectorSvg(snapshot)
  const svgPath = join(outDir, 'audit.svg')
  writeFileSync(svgPath, vector.svg, 'utf8')
  check('svg_has_text', vector.svg.includes('<text'), 'real SVG text')
  check('svg_has_path', vector.svg.includes('<path'), 'vector edges')
  check('svg_has_noto', vector.svg.includes('Noto Sans SC'), 'font-family')
  const topicText = String(nodes.find((n) => n.id === 'topic')?.text ?? '').slice(0, 2)
  if (topicText) {
    check('svg_has_topic_chars', vector.svg.includes(topicText), topicText)
  }

  const t0 = Date.now()
  const pdf = await buildA4PdfFromMindMapVectors(
    [{ vector, headerCapture: null }],
    vector.width >= vector.height ? 'landscape' : 'portrait'
  )
  const pdfMs = Date.now() - t0
  const pdfArray = pdf.output('arraybuffer')
  const pdfBuf = Buffer.from(pdfArray)
  const pdfPath = join(outDir, 'audit.pdf')
  writeFileSync(pdfPath, pdfBuf)
  const pdfKb = pdfBuf.length / 1024
  const pdfMb = pdfBuf.length / (1024 * 1024)
  audit.pdf = {
    path: pdfPath,
    bytes: pdfBuf.length,
    kb: Number(pdfKb.toFixed(1)),
    mb: Number(pdfMb.toFixed(3)),
    buildMs: pdfMs,
  }
  check('pdf_magic', pdfBuf.subarray(0, 4).toString() === '%PDF', 'PDF header')
  check('pdf_not_huge', pdfBuf.length < 5 * 1024 * 1024, `${pdfKb.toFixed(1)} KB (subset expected << 16MB font)`)
  check('pdf_not_empty', pdfBuf.length > 10_000, `${pdfKb.toFixed(1)} KB`)

  // DOCX path: high-DPI PNG from SVG via sharp (geometry check); then python-docx builder
  let pngBuf
  try {
    const sharp = (await import('sharp')).default
    pngBuf = await sharp(Buffer.from(vector.svg), { density: 300 })
      .png()
      .toBuffer()
    const pngPath = join(outDir, 'audit-docx-diagram.png')
    writeFileSync(pngPath, pngBuf)
    audit.docxPng = {
      path: pngPath,
      bytes: pngBuf.length,
      kb: Number((pngBuf.length / 1024).toFixed(1)),
    }
    check('docx_png', pngBuf.length > 5_000, `${audit.docxPng.kb} KB @300dpi`)
  } catch (error) {
    check('docx_png', false, String(error))
  }

  if (pngBuf) {
    // Call Python worksheet builder
    const { spawnSync } = await import('node:child_process')
    const py = spawnSync(
      '/home/royw/miniconda3/envs/python313/bin/python',
      [
        '-c',
        `
from pathlib import Path
from services.diagram.worksheet_docx import WorksheetDocxSpec, WorksheetDocxLabels, build_worksheet_docx
png = Path(${JSON.stringify(join(outDir, 'audit-docx-diagram.png'))}).read_bytes()
spec = WorksheetDocxSpec(
    title=${JSON.stringify(fixture.data.title || 'audit')},
    layout='landscape',
    show_topic=True,
    show_name=True,
    show_class=True,
    show_date=True,
    show_instruction=True,
    topic_text=${JSON.stringify(fixture.data.title || 'audit')},
    instruction_text='',
    diagram_offset_x=0,
    diagram_offset_y=0,
    diagram_scale=1,
    labels=WorksheetDocxLabels(
        name='Name',
        class_name='Class',
        date='Date',
        instruction_prefix='Instruction: ',
        default_instruction='Complete the mind map.',
    ),
)
out = Path(${JSON.stringify(join(outDir, 'audit.docx'))})
out.write_bytes(build_worksheet_docx(spec, png))
print(out.stat().st_size)
`,
      ],
      { cwd: repoRoot, encoding: 'utf8' }
    )
    if (py.status === 0) {
      const docxBytes = Number(py.stdout.trim())
      audit.docx = {
        path: join(outDir, 'audit.docx'),
        bytes: docxBytes,
        kb: Number((docxBytes / 1024).toFixed(1)),
      }
      check('docx_built', docxBytes > 10_000, `${audit.docx.kb} KB`)
    } else {
      check('docx_built', false, py.stderr || py.stdout || 'python failed')
    }
  }

  audit.ok = audit.errors.length === 0
  writeFileSync(join(outDir, 'audit.json'), JSON.stringify(audit, null, 2))
  console.log(JSON.stringify(audit, null, 2))
  process.exit(audit.ok ? 0 : 1)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
