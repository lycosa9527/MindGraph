/**
 * Toolbar font values are desktop face names (SimSun, KaiTi, Inter).
 * A phone does not ship those faces, so `font-family: SimSun` paints the same
 * fallback as the default stack. Each menu value maps to a stack that prefers
 * the local face, then a face iOS ships, then a webfont loaded on demand.
 */
import type { DiagramData } from '@/types'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

/** Stored `style.fontFamily` token → CSS font-family used when painting and measuring. */
export const DIAGRAM_CANVAS_FONT_STACKS: Record<string, string> = {
  SimSun: "SimSun, 'Songti SC', 'STSong', 'Noto Serif SC', serif",
  KaiTi: "KaiTi, 'Kaiti SC', 'STKaiti', 'LXGW WenKai Screen', serif",
  Inter: "Inter, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  'Space Grotesk': "'Space Grotesk', 'Noto Sans SC', 'PingFang SC', sans-serif",
  'Microsoft YaHei': "'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', sans-serif",
  Arial: "Arial, 'Noto Sans', 'Noto Sans SC', sans-serif",
}

const WEBFONT_TOKENS = new Set(['SimSun', 'KaiTi', 'Inter', 'Space Grotesk'])

const loadedTokens = new Set<string>()
const inflightTokens = new Map<string, Promise<void>>()

export function diagramPaintFontFamily(
  stored: string | null | undefined,
  fallback: string = DIAGRAM_NODE_FONT_STACK
): string {
  const token = stored?.trim()
  if (!token) return fallback
  return DIAGRAM_CANVAS_FONT_STACKS[token] ?? token
}

function rememberLoaded(token: string, job: Promise<void>): Promise<void> {
  const tracked = job.then(
    () => {
      loadedTokens.add(token)
    },
    () => undefined
  )
  inflightTokens.set(token, tracked)
  void tracked.finally(() => {
    inflightTokens.delete(token)
  })
  return tracked
}

function loadDiagramCanvasWebfont(token: string): Promise<void> {
  if (token === 'SimSun') {
    return Promise.all([
      import('@fontsource/noto-serif-sc/chinese-simplified-400.css'),
      import('@fontsource/noto-serif-sc/chinese-simplified-700.css'),
      import('@fontsource/noto-serif-sc/latin-400.css'),
      import('@fontsource/noto-serif-sc/latin-700.css'),
    ]).then(() => undefined)
  }
  if (token === 'KaiTi') {
    return import('lxgw-wenkai-screen-webfont/lxgwwenkaiscreen.css').then(() => undefined)
  }
  if (token === 'Inter') {
    return Promise.all([
      import('@fontsource/inter/latin-400.css'),
      import('@fontsource/inter/latin-700.css'),
      import('@fontsource/inter/latin-ext-400.css'),
      import('@fontsource/inter/latin-ext-700.css'),
    ]).then(() => undefined)
  }
  if (token === 'Space Grotesk') {
    return Promise.all([
      import('@fontsource/space-grotesk/latin-400.css'),
      import('@fontsource/space-grotesk/latin-700.css'),
    ]).then(() => undefined)
  }
  return Promise.resolve()
}

/** Register webfonts for menu tokens the open diagram (or the picker) actually uses. */
export function ensureDiagramCanvasFonts(tokens: Iterable<string>): Promise<void> {
  const jobs: Promise<void>[] = []
  for (const raw of tokens) {
    const token = raw.trim()
    if (!WEBFONT_TOKENS.has(token) || loadedTokens.has(token)) continue
    const existing = inflightTokens.get(token)
    jobs.push(existing ?? rememberLoaded(token, loadDiagramCanvasWebfont(token)))
  }
  if (jobs.length === 0) return Promise.resolve()
  return Promise.all(jobs).then(() => {
    if (typeof document !== 'undefined' && document.fonts?.ready) {
      return document.fonts.ready.then(() => undefined)
    }
    return undefined
  })
}

function pushToken(seen: Set<string>, out: string[], stored: string | null | undefined): void {
  const token = stored?.trim()
  if (!token || !WEBFONT_TOKENS.has(token) || seen.has(token)) return
  seen.add(token)
  out.push(token)
}

/** Webfont tokens stored on nodes or in mind-map `_node_styles`. */
export function diagramFontTokensInUse(data: DiagramData | null | undefined): string[] {
  if (!data) return []
  const seen = new Set<string>()
  const out: string[] = []
  for (const node of data.nodes ?? []) {
    pushToken(seen, out, node.style?.fontFamily)
  }
  const styles = data._node_styles
  if (styles) {
    for (const style of Object.values(styles)) {
      pushToken(seen, out, style?.fontFamily)
    }
  }
  return out
}
