/**
 * Per-diagram caption drafts for library demo mode.
 * Seeds come from sidebar.demo.caption.*; edits live in localStorage.
 */
import DOMPurify from 'dompurify'

import { APP_REFINED_SANS_STACK } from '@/utils/diagramNodeFontStack'

export const DEMO_CAPTION_STORAGE_KEY = 'mg.libraryDemo.captions.v1'

export const DEMO_FONT_SIZES = [15, 18, 22, 28] as const
export type DemoFontSize = (typeof DEMO_FONT_SIZES)[number]
export const DEMO_FONT_FACES = ['sans', 'sc', 'tc', 'serif', 'song', 'kai', 'mono'] as const
export type DemoFontFace = (typeof DEMO_FONT_FACES)[number]
export const DEMO_FONT_COLORS = ['ink', 'stone', 'brown', 'red', 'blue', 'green'] as const
export type DemoFontColor = (typeof DEMO_FONT_COLORS)[number]

export interface DemoCaptionDraft {
  text: string
  /** Sanitized rich text. Absent on older drafts; the plain `text` is used. */
  html?: string
  fontSize: DemoFontSize
  fontFace: DemoFontFace
  fontColor: DemoFontColor
}

const CAPTION_TYPES = [
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
  'mindmap',
  'concept_map',
] as const

const SC_STACK = "'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
const TC_STACK = "'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', sans-serif"
const SERIF_STACK =
  "Georgia, 'Iowan Old Style', Palatino, 'Palatino Linotype', 'Songti SC', 'Noto Serif SC', serif"
const SONG_STACK = "'Songti SC', 'Noto Serif SC', 'SimSun', 'STSong', serif"
const KAI_STACK = "'KaiTi', 'STKaiti', 'Kaiti SC', 'Songti SC', serif"
const MONO_STACK = "ui-monospace, 'Cascadia Code', 'Source Code Pro', monospace"
const SAFE_STYLE = /^(font-size|font-family|font-weight|font-style|text-decoration)\s*:/i
const COLOR_HEX: Record<DemoFontColor, string> = {
  ink: '#1c1917',
  stone: '#78716c',
  brown: '#9a3412',
  red: '#b91c1c',
  blue: '#1e3a8a',
  green: '#166534',
}
const ALLOWED_COLOR_HEX = new Set(Object.values(COLOR_HEX))

export function demoCaptionMessageKey(diagramType: string): string {
  const normalized = diagramType === 'mind_map' ? 'mindmap' : diagramType
  if ((CAPTION_TYPES as readonly string[]).includes(normalized)) {
    return `sidebar.demo.caption.${normalized}`
  }
  return 'sidebar.demo.caption.fallback'
}

export function demoFontFamily(face: DemoFontFace): string {
  if (face === 'sc') return SC_STACK
  if (face === 'tc') return TC_STACK
  if (face === 'serif') return SERIF_STACK
  if (face === 'song') return SONG_STACK
  if (face === 'kai') return KAI_STACK
  if (face === 'mono') return MONO_STACK
  return APP_REFINED_SANS_STACK
}

export function demoFontColor(color: DemoFontColor | undefined): string {
  if (color && color in COLOR_HEX) return COLOR_HEX[color]
  return COLOR_HEX.ink
}

function isAllowedColorDecl(decl: string): boolean {
  const match = /^color\s*:\s*(#[0-9a-f]{6})$/i.exec(decl)
  if (!match?.[1]) return false
  return ALLOWED_COLOR_HEX.has(match[1].toLowerCase())
}

export function escapeDemoCaptionText(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function scrubCaptionStyles(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  for (const el of doc.body.querySelectorAll('[style]')) {
    const keep: string[] = []
    for (const decl of el.getAttribute('style')?.split(';') ?? []) {
      const trimmed = decl.trim()
      if (/url\s*\(|expression/i.test(trimmed)) continue
      if (SAFE_STYLE.test(trimmed) || isAllowedColorDecl(trimmed)) {
        keep.push(trimmed)
      }
    }
    if (keep.length > 0) el.setAttribute('style', keep.join('; '))
    else el.removeAttribute('style')
  }
  return doc.body.innerHTML
}

export function sanitizeDemoCaptionHtml(html: string): string {
  const clean = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['p', 'br', 'div', 'span', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li'],
    ALLOWED_ATTR: ['style'],
  })
  return scrubCaptionStyles(clean)
}

export function demoCaptionHtml(draft: DemoCaptionDraft): string {
  if (draft.html) return sanitizeDemoCaptionHtml(draft.html)
  const body = escapeDemoCaptionText(draft.text).replace(/\n/g, '<br>')
  return `<p>${body}</p>`
}

export function isDemoFontSize(value: number): value is DemoFontSize {
  return (DEMO_FONT_SIZES as readonly number[]).includes(value)
}

function parseColor(value: unknown): DemoFontColor {
  if (typeof value === 'string' && (DEMO_FONT_COLORS as readonly string[]).includes(value)) {
    return value as DemoFontColor
  }
  return 'ink'
}

function parseFace(value: unknown): DemoFontFace {
  if (typeof value === 'string' && (DEMO_FONT_FACES as readonly string[]).includes(value)) {
    return value as DemoFontFace
  }
  return 'sans'
}

export function parseStoredDemoCaption(value: unknown): DemoCaptionDraft | null {
  if (!value || typeof value !== 'object') return null
  const record = value as {
    text?: unknown
    html?: unknown
    fontSize?: unknown
    fontFace?: unknown
    fontColor?: unknown
  }
  if (typeof record.text !== 'string') return null
  const fontSize = typeof record.fontSize === 'number' ? record.fontSize : 18
  if (!isDemoFontSize(fontSize)) return null
  const draft: DemoCaptionDraft = {
    text: record.text,
    fontSize,
    fontFace: parseFace(record.fontFace),
    fontColor: parseColor(record.fontColor),
  }
  if (typeof record.html === 'string' && record.html.trim()) {
    draft.html = sanitizeDemoCaptionHtml(record.html)
  }
  return draft
}

export function readDemoCaptionStore(raw: string | null): Record<string, DemoCaptionDraft> {
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object') return {}
    const out: Record<string, DemoCaptionDraft> = {}
    for (const [id, value] of Object.entries(parsed)) {
      const draft = parseStoredDemoCaption(value)
      if (draft) out[id] = draft
    }
    return out
  } catch {
    return {}
  }
}

export function seedDemoCaption(
  diagramType: string,
  title: string,
  translate: (key: string, params: Record<string, string>) => string,
  stored: DemoCaptionDraft | undefined
): DemoCaptionDraft {
  if (stored) return stored
  const text = translate(demoCaptionMessageKey(diagramType), { title })
  return {
    text,
    html: `<p>${escapeDemoCaptionText(text)}</p>`,
    fontSize: 18,
    fontFace: 'sans',
    fontColor: 'ink',
  }
}
