/**
 * Presentation highlighter: default stroke and palette (semi-transparent rgba for SVG).
 */

export const DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR = 'rgba(255, 235, 60, 0.48)'

/** Presentation pen tool: fixed blue stroke (rgba for SVG) */
export const DEFAULT_PRESENTATION_PEN_COLOR = 'rgba(37, 99, 235, 0.9)'

export interface PresentationHighlighterPaletteEntry {
  /** Opaque swatch for UI (circle) */
  swatch: string
  /** SVG stroke value */
  stroke: string
}

export const PRESENTATION_HIGHLIGHTER_PALETTE: PresentationHighlighterPaletteEntry[] = [
  { swatch: '#fde047', stroke: 'rgba(255, 235, 60, 0.48)' },
  { swatch: '#4ade80', stroke: 'rgba(74, 222, 128, 0.5)' },
  { swatch: '#f472b6', stroke: 'rgba(244, 114, 182, 0.5)' },
  { swatch: '#fb923c', stroke: 'rgba(251, 146, 60, 0.5)' },
  { swatch: '#38bdf8', stroke: 'rgba(56, 189, 248, 0.5)' },
  { swatch: '#a78bfa', stroke: 'rgba(167, 139, 250, 0.5)' },
  { swatch: '#facc15', stroke: 'rgba(250, 204, 21, 0.5)' },
  { swatch: '#94a3b8', stroke: 'rgba(148, 163, 184, 0.55)' },
]
