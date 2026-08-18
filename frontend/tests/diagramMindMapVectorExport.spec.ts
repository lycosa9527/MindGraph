import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import type { Connection } from '@/types'
import { buildMindMapVectorSnapshot } from '@/utils/diagramMindMapVectorModel'
import { renderMindMapVectorNode } from '@/utils/diagramMindMapVectorNodes'
import {
  escapeXml,
  mindMapExportPlainText,
  mindMapSvgTextBaselineY,
  parseMindMapExportText,
  wrapMindMapExportLines,
} from '@/utils/diagramMindMapVectorText'
import {
  buildMindMapVectorSvg,
  computeMindMapVectorBounds,
} from '@/utils/diagramMindMapVectorSvg'
import { mindMapVectorEdgeStrokeColor } from '@/utils/diagramMindMapVectorEdges'
import {
  __clearMindMapVectorPdfFontCacheForTests,
  __setMindMapVectorPdfFontCacheForTests,
  registerMindMapVectorPdfFonts,
} from '@/utils/diagramMindMapVectorPdfFonts'
import { buildA4PdfFromMindMapVectors } from '@/utils/diagramMindMapVectorPdf'
import { rasterizeMindMapVectorSvg } from '@/utils/diagramMindMapVectorRaster'

vi.mock('@/utils/diagramExportHtmlToImage', () => ({
  loadHtmlToImageModule: async () => ({
    toBlob: async () => new Blob([new Uint8Array([1, 2, 3])], { type: 'image/png' }),
  }),
}))

function tinyMindMapSnapshot(shape: 'rounded' | 'underline' = 'rounded') {
  return buildMindMapVectorSnapshot({
    canvasMode: 'v2',
    outlineWireframe: false,
    store: {
      type: 'mind_map',
      mindMapTopicActualWidth: 120,
      mindMapNodeWidths: { topic: 120, 'branch-r-1-0': 100 },
      mindMapNodeHeights: { topic: 40, 'branch-r-1-0': 34 },
      nodeDimensions: {},
      data: {
        type: 'mind_map',
        nodes: [
          {
            id: 'topic',
            text: '主题 **重点**',
            type: 'topic',
            position: { x: 200, y: 200 },
            style: { nodeShape: 'rectangle', borderColor: '#2563eb' },
          },
          {
            id: 'branch-r-1-0',
            text: 'Branch <one>',
            type: 'branch',
            position: { x: 400, y: 180 },
            style: { nodeShape: shape },
            parentId: 'topic',
          },
        ],
        connections: [
          {
            id: 'e1',
            source: 'topic',
            target: 'branch-r-1-0',
          } satisfies Connection,
        ],
        _mindmap_diagram_style: 'classic',
      },
    },
  })
}

describe('diagramMindMapVectorText', () => {
  it('drops the first-line baseline below the old 0.85 line-box fudge', () => {
    const fontSize = 16
    const lineHeight = fontSize * 1.4
    const next = mindMapSvgTextBaselineY({
      boxY: 0,
      boxHeight: 42,
      blockHeight: lineHeight,
      fontSize,
      lineHeight,
      paddingY: 9,
      borderWidth: 1.5,
    })
    const previous = Math.max(9, (42 - lineHeight) / 2) + fontSize * 0.85
    expect(next).toBeGreaterThan(previous)
  })

  it('escapes XML', () => {
    expect(escapeXml('a<b>&"\'')).toContain('&lt;')
    expect(escapeXml('a<b>&"\'')).toContain('&amp;')
  })

  it('parses bold and strips math/code noise', () => {
    const spans = parseMindMapExportText('Hello **world** and $x^2$ plus `code`')
    const plain = mindMapExportPlainText('Hello **world** and $x^2$ plus `code`')
    expect(spans.some((s) => s.bold && s.text.includes('world'))).toBe(true)
    expect(plain).toContain('Hello')
    expect(plain).toContain('world')
    expect(plain).not.toContain('$')
    expect(plain).not.toContain('`')
  })

  it('delegates wrapping to shared mindMapTextWrap', () => {
    const lines = wrapMindMapExportLines('abcdefghijabcdefghij', 36, 14)
    expect(lines.length).toBeGreaterThan(1)
    expect(wrapMindMapExportLines('中心主题', 200, 18, { fontWeight: 'bold' })).toEqual([
      '中心主题',
    ])
  })
})

describe('diagramMindMapVector numbering chrome', () => {
  it('keeps body text separate from prefix chrome', () => {
    const snapshot = buildMindMapVectorSnapshot({
      canvasMode: 'v2',
      outlineWireframe: false,
      store: {
        type: 'mind_map',
        mindMapTopicActualWidth: 120,
        mindMapNodeWidths: { topic: 120, 'branch-r-1-0': 140 },
        mindMapNodeHeights: { topic: 40, 'branch-r-1-0': 34 },
        nodeDimensions: {},
        data: {
          type: 'mind_map',
          _mindmap_branch_numbering: true,
          _mindmap_branch_numbering_prefix: 'chineseChapter',
          _mindmap_branch_numbering_nested: 'outline',
          nodes: [
            {
              id: 'topic',
              text: '主题',
              type: 'topic',
              position: { x: 200, y: 200 },
              style: { nodeShape: 'rectangle' },
            },
            {
              id: 'uid-intro',
              text: '引言',
              type: 'branch',
              position: { x: 400, y: 180 },
              style: { nodeShape: 'rounded' },
              parentId: 'topic',
            },
          ],
          connections: [{ id: 'e1', source: 'topic', target: 'uid-intro' } satisfies Connection],
        },
      },
    })
    expect(snapshot).not.toBeNull()
    if (!snapshot) return
    const branch = snapshot.nodes.find((node) => node.id === 'uid-intro')
    expect(branch?.text).toBe('引言')
    expect(branch?.numberPrefix).toBe('第一章')
    const nodeSvg = renderMindMapVectorNode(branch!, {
      diagramStyleId: 'classic',
      outlineWireframe: false,
    })
    expect(nodeSvg).toContain('第一章')
    expect(nodeSvg).toContain('引言')
    expect(nodeSvg).not.toContain('第一章 引言')
  })
})

describe('diagramMindMapVectorSvg', () => {
  it('builds SVG with real text, paths, and viewBox covering nodes', () => {
    const snapshot = tinyMindMapSnapshot('rounded')
    expect(snapshot).not.toBeNull()
    if (!snapshot) return

    const result = buildMindMapVectorSvg(snapshot)
    expect(result.svg).toContain('<svg')
    expect(result.svg).toContain('<text')
    expect(result.svg).toContain('<path')
    expect(result.svg).toContain('主题')
    expect(result.svg).toContain('Branch')
    expect(result.svg).toContain('&lt;one&gt;')
    expect(result.svg).toContain('rx=')

    const bounds = computeMindMapVectorBounds(snapshot)
    expect(bounds.width).toBeGreaterThan(100)
    expect(bounds.minX).toBeLessThanOrEqual(200)
  })

  it('emits underline connector geometry for underline branches', () => {
    const snapshot = tinyMindMapSnapshot('underline')
    expect(snapshot).not.toBeNull()
    if (!snapshot) return
    const nodeSvg = renderMindMapVectorNode(snapshot.nodes[1], {
      diagramStyleId: 'classic',
      outlineWireframe: false,
    })
    expect(nodeSvg).toContain('<text')
    const full = buildMindMapVectorSvg(snapshot)
    expect(full.svg).toMatch(/M [\d.]+ [\d.]+ L [\d.]+ [\d.]+/)
  })

  it('uses outline stroke in wireframe mode', () => {
    expect(mindMapVectorEdgeStrokeColor({ borderColor: '#2563eb' }, true)).not.toBe('#2563eb')
  })
})

describe('diagramMindMapVectorPdfFonts', () => {
  beforeEach(() => {
    __setMindMapVectorPdfFontCacheForTests([
      {
        vfsName: 'NotoSansSC-Regular.ttf',
        family: 'Noto Sans SC',
        style: 'normal',
        base64: btoa('00000000000000000000'),
      },
    ])
  })

  afterEach(() => {
    __clearMindMapVectorPdfFontCacheForTests()
  })

  it('registers override fonts on jsPDF-like doc', async () => {
    const doc = {
      addFileToVFS: vi.fn(),
      addFont: vi.fn(),
    }
    await registerMindMapVectorPdfFonts(doc)
    expect(doc.addFileToVFS).toHaveBeenCalled()
    expect(doc.addFont).toHaveBeenCalledWith(
      'NotoSansSC-Regular.ttf',
      'Noto Sans SC',
      'normal'
    )
  })

  it('rejects empty PDF page lists', async () => {
    await expect(buildA4PdfFromMindMapVectors([], 'landscape')).rejects.toThrow(
      /at least one page/
    )
  })
})

describe('diagramMindMapVectorRaster', () => {
  it('rasterizes SVG to a non-empty PNG blob', async () => {
    const snapshot = tinyMindMapSnapshot()
    expect(snapshot).not.toBeNull()
    if (!snapshot) return
    const { svg } = buildMindMapVectorSvg(snapshot)
    const result = await rasterizeMindMapVectorSvg(svg, { pixelRatio: 2 })
    expect(result.blob.size).toBeGreaterThan(0)
    expect(result.width).toBeGreaterThan(0)
    expect(result.height).toBeGreaterThan(0)
  })
})
