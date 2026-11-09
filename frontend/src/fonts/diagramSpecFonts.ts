/**
 * Load the faces a diagram paints with before its first layout.
 * Fontsource CSS only registers faces; the browser fetches one when text first
 * uses it, and `document.fonts.ready` does not wait for faces nobody asked for.
 * Without this, layout measures fallback metrics and every node moves once the
 * real face arrives.
 */
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import type { DiagramData } from '@/types'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

import {
  diagramFontTokensInUse,
  diagramPaintFontFamily,
  ensureDiagramCanvasFonts,
} from './diagramCanvasFonts'

/** A face that never arrives must not hold the diagram back. */
const DIAGRAM_FONT_LOAD_TIMEOUT_MS = 1000
const DIAGRAM_FONT_WEIGHTS = ['400', '700'] as const

function specCharacters(spec: unknown): string {
  try {
    return [...new Set(JSON.stringify(spec) ?? '')].join('')
  } catch {
    return ''
  }
}

function loadFaces(stacks: Iterable<string>, text: string): Promise<void> {
  const jobs: Promise<unknown>[] = []
  for (const stack of stacks) {
    for (const weight of DIAGRAM_FONT_WEIGHTS) {
      jobs.push(document.fonts.load(`${weight} 16px ${stack}`, text).catch(() => undefined))
    }
  }
  return Promise.all(jobs).then(() => undefined)
}

export function loadDiagramFontsForSpec(spec: Record<string, unknown>): Promise<void> {
  if (typeof document === 'undefined' || typeof document.fonts?.load !== 'function') {
    return Promise.resolve()
  }
  const text = specCharacters(spec)
  if (!text) return Promise.resolve()
  const tokens = diagramFontTokensInUse(spec as unknown as DiagramData)
  const stacks = new Set([
    DIAGRAM_NODE_FONT_STACK,
    MIND_MAP_GEOMETRY.fontFamily,
    ...tokens.map((token) => diagramPaintFontFamily(token)),
  ])
  const ready = ensureDiagramCanvasFonts(tokens).then(() => loadFaces(stacks, text))
  const timeout = new Promise<void>((resolve) => {
    window.setTimeout(resolve, DIAGRAM_FONT_LOAD_TIMEOUT_MS)
  })
  return Promise.race([ready, timeout])
}
