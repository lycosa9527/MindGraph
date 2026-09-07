export const V3_RIBBON_TABS = ['file', 'edit', 'ai', 'teaching', 'research'] as const

export type V3RibbonTabId = (typeof V3_RIBBON_TABS)[number]

const V3_RIBBON_TAB_ALIASES: Record<string, V3RibbonTabId> = {
  home: 'edit',
  draw: 'edit',
  style: 'edit',
  insert: 'edit',
  design: 'edit',
  learn: 'teaching',
  review: 'teaching',
}

const V3_RIBBON_TAB_SET = new Set<string>(V3_RIBBON_TABS)

export function isV3RibbonTabId(value: string | null | undefined): value is V3RibbonTabId {
  return typeof value === 'string' && V3_RIBBON_TAB_SET.has(value)
}

export function normalizeV3RibbonTabId(value: string | null | undefined): V3RibbonTabId | null {
  if (typeof value !== 'string') return null
  const id = value.trim().toLowerCase()
  const mapped = V3_RIBBON_TAB_ALIASES[id] ?? id
  return isV3RibbonTabId(mapped) ? mapped : null
}

export const V3_RIBBON_TAB_LABEL_KEYS: Record<V3RibbonTabId, string> = {
  file: 'canvas.v3.ribbon.tabFile',
  edit: 'canvas.v3.ribbon.tabEdit',
  ai: 'canvas.v3.ribbon.tabDraw',
  teaching: 'canvas.v3.ribbon.tabTeaching',
  research: 'canvas.v3.ribbon.tabResearch',
}

export const DEFAULT_V3_RIBBON_TAB: V3RibbonTabId = 'edit'
