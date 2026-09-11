export const MIND_MAP_RIBBON_TABS = ['file', 'edit', 'ai', 'teaching', 'research'] as const

export type MindMapRibbonTabId = (typeof MIND_MAP_RIBBON_TABS)[number]

const MIND_MAP_RIBBON_TAB_ALIASES: Record<string, MindMapRibbonTabId> = {
  home: 'edit',
  draw: 'edit',
  style: 'edit',
  insert: 'edit',
  design: 'edit',
  learn: 'teaching',
  review: 'teaching',
}

const MIND_MAP_RIBBON_TAB_SET = new Set<string>(MIND_MAP_RIBBON_TABS)

export function isMindMapRibbonTabId(value: string | null | undefined): value is MindMapRibbonTabId {
  return typeof value === 'string' && MIND_MAP_RIBBON_TAB_SET.has(value)
}

export function normalizeMindMapRibbonTabId(value: string | null | undefined): MindMapRibbonTabId | null {
  if (typeof value !== 'string') return null
  const id = value.trim().toLowerCase()
  const mapped = MIND_MAP_RIBBON_TAB_ALIASES[id] ?? id
  return isMindMapRibbonTabId(mapped) ? mapped : null
}

export const MIND_MAP_RIBBON_TAB_LABEL_KEYS: Record<MindMapRibbonTabId, string> = {
  file: 'canvas.ribbon.tabFile',
  edit: 'canvas.ribbon.tabEdit',
  ai: 'canvas.ribbon.tabDraw',
  teaching: 'canvas.ribbon.tabTeaching',
  research: 'canvas.ribbon.tabResearch',
}

export const DEFAULT_MIND_MAP_RIBBON_TAB: MindMapRibbonTabId = 'edit'

/**
 * Tab to show when opening a canvas. File is a destination, not a landing tab —
 * a saved `file` preference still opens Edit (same as Word Home vs File).
 */
export function resolveLandingMindMapRibbonTab(
  value: string | null | undefined
): MindMapRibbonTabId {
  const tab = normalizeMindMapRibbonTabId(value) ?? DEFAULT_MIND_MAP_RIBBON_TAB
  return tab === 'file' ? DEFAULT_MIND_MAP_RIBBON_TAB : tab
}
