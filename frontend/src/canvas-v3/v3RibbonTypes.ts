export const V3_RIBBON_TABS = ['file', 'home', 'design', 'review', 'ai'] as const

export type V3RibbonTabId = (typeof V3_RIBBON_TABS)[number]

export function isV3RibbonTabId(value: string | null | undefined): value is V3RibbonTabId {
  return (
    value === 'file' ||
    value === 'home' ||
    value === 'design' ||
    value === 'review' ||
    value === 'ai'
  )
}

export const V3_RIBBON_TAB_LABEL_KEYS: Record<V3RibbonTabId, string> = {
  file: 'canvas.v3.ribbon.tabFile',
  home: 'canvas.v3.ribbon.tabHome',
  design: 'canvas.v3.ribbon.tabDesign',
  review: 'canvas.v3.ribbon.tabReview',
  ai: 'canvas.v3.ribbon.tabAi',
}

export const DEFAULT_V3_RIBBON_TAB: V3RibbonTabId = 'home'
