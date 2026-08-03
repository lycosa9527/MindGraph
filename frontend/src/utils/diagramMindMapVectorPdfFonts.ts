/**
 * Offline jsPDF font registration for mind-map vector PDF export.
 *
 * Fonts load from same-origin ``/api/mindmap_export_fonts/...`` (COS-backed API
 * with local cache). No CDN. Faces must be TrueType (glyf) — jsPDF cannot
 * encode Noto CJK OTF/CFF.
 *
 * Do not import ``subset-font`` / ``fontverter`` here: their wawoff2 binding uses
 * ``new Function`` and violates the app Content-Security-Policy (no unsafe-eval).
 * Fonts are already TrueType from ``npm run vendor:mindmap-export-fonts``.
 *
 * Publish fonts to COS:
 *   python scripts/db/publish_mindmap_export_fonts_to_cos.py
 */
import { MIND_MAP_VECTOR_PDF_FONT_NOTO } from '@/utils/diagramMindMapVectorText'

type JsPdfFontDoc = {
  addFileToVFS: (filename: string, data: string) => void
  addFont: (filename: string, fontName: string, fontStyle: string) => void
}

type CachedFontBytes = {
  vfsName: string
  family: string
  style: 'normal' | 'bold'
  bytes: ArrayBuffer
}

type RegisteredFont = {
  vfsName: string
  family: string
  style: 'normal' | 'bold'
  base64: string
}

const fontBytesCache = new Map<string, CachedFontBytes>()
let testFontsOverride: RegisteredFont[] | null = null

const TRUETYPE_SFNT = 0x00010000

/**
 * Same-origin API (COS → server cache → browser). Local ``/fonts/`` remains a
 * last-resort fallback for offline dev without the API.
 */
const FONT_SOURCES: Array<{
  key: string
  family: string
  style: 'normal' | 'bold'
  vfsName: string
  paths: string[]
  required: boolean
}> = [
  {
    key: 'noto-sc-normal',
    family: MIND_MAP_VECTOR_PDF_FONT_NOTO,
    style: 'normal',
    vfsName: 'NotoSansSC-Regular.ttf',
    paths: [
      '/api/mindmap_export_fonts/NotoSansSC-Regular.ttf',
      '/fonts/NotoSansSC-Regular.ttf',
    ],
    required: true,
  },
  {
    key: 'noto-sc-bold',
    family: MIND_MAP_VECTOR_PDF_FONT_NOTO,
    style: 'bold',
    vfsName: 'NotoSansSC-Bold.ttf',
    paths: ['/api/mindmap_export_fonts/NotoSansSC-Bold.ttf', '/fonts/NotoSansSC-Bold.ttf'],
    required: false,
  },
]

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  const chunkSize = 0x8000
  let binary = ''
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, Math.min(i + chunkSize, bytes.length))
    binary += String.fromCharCode(...chunk)
  }
  return btoa(binary)
}

function isTrueTypeSfnt(buffer: ArrayBuffer): boolean {
  if (buffer.byteLength < 4) return false
  return new DataView(buffer).getUint32(0, false) === TRUETYPE_SFNT
}

async function loadLocalFontBytes(paths: string[]): Promise<ArrayBuffer> {
  let lastError: unknown
  for (const path of paths) {
    try {
      const response = await fetch(path, { cache: 'force-cache', credentials: 'same-origin' })
      if (!response.ok) {
        throw new Error(`Export font fetch failed (${response.status}): ${path}`)
      }
      const buffer = await response.arrayBuffer()
      if (buffer.byteLength < 1024) {
        throw new Error(`Export font too small: ${path}`)
      }
      if (!isTrueTypeSfnt(buffer)) {
        throw new Error(
          `Export font is not TrueType: ${path}. ` +
            'Re-run `npm run vendor:mindmap-export-fonts` and republish to COS.'
        )
      }
      return buffer
    } catch (error) {
      lastError = error
    }
  }
  throw lastError instanceof Error
    ? lastError
    : new Error(
        'Export fonts unavailable. Publish with ' +
          '`python scripts/db/publish_mindmap_export_fonts_to_cos.py` ' +
          'or run `npm run vendor:mindmap-export-fonts`.'
      )
}

async function ensureFontBytes(
  entry: (typeof FONT_SOURCES)[number]
): Promise<CachedFontBytes> {
  const hit = fontBytesCache.get(entry.key)
  if (hit) return hit
  const bytes = await loadLocalFontBytes(entry.paths)
  const cached: CachedFontBytes = {
    vfsName: entry.vfsName,
    family: entry.family,
    style: entry.style,
    bytes,
  }
  fontBytesCache.set(entry.key, cached)
  return cached
}

function registerCached(doc: JsPdfFontDoc, font: RegisteredFont): void {
  doc.addFileToVFS(font.vfsName, font.base64)
  doc.addFont(font.vfsName, font.family, font.style)
}

/**
 * Register Noto Sans SC on a jsPDF document from COS-backed same-origin fonts.
 *
 * ``textForSubset`` is kept for API compatibility; browser CSP forbids the
 * subset-font/wawoff2 toolchain, so the full TrueType face is embedded.
 */
export async function registerMindMapVectorPdfFonts(
  doc: JsPdfFontDoc,
  _textForSubset = ''
): Promise<void> {
  if (testFontsOverride) {
    for (const font of testFontsOverride) {
      registerCached(doc, font)
    }
    return
  }

  for (const entry of FONT_SOURCES) {
    try {
      const cached = await ensureFontBytes(entry)
      registerCached(doc, {
        vfsName: cached.vfsName,
        family: cached.family,
        style: cached.style,
        base64: arrayBufferToBase64(cached.bytes),
      })
    } catch (error) {
      if (entry.required) {
        throw error
      }
    }
  }
}

/** Collect text from vector SVG pages for font subsetting (API compat / future). */
export function collectMindMapVectorPdfSubsetText(svgStrings: string[]): string {
  const chunks: string[] = []
  for (const svg of svgStrings) {
    chunks.push(svg.replace(/<[^>]+>/g, ' '))
  }
  return chunks.join(' ')
}

/** Inject fonts for Vitest (skip filesystem). */
export function __setMindMapVectorPdfFontCacheForTests(fonts: RegisteredFont[] | null): void {
  testFontsOverride = fonts
  fontBytesCache.clear()
}

export function __clearMindMapVectorPdfFontCacheForTests(): void {
  testFontsOverride = null
  fontBytesCache.clear()
}
