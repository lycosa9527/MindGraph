/**
 * 新功能开发 sidebar navigation (top-level panel tab).
 */
import { settingsSubtabRequiresCapabilities } from '@/utils/adminCapabilities'

export type FeatureDevSubtab = 'smart_response' | 'kitty_llmops' | 'teacher_usage'

export interface FeatureDevNavLeafItem {
  kind: 'leaf'
  name: FeatureDevSubtab
  labelKey: string
}

export type FeatureDevNavItem = FeatureDevNavLeafItem

export const FEATURE_DEV_NAV_ITEMS: readonly FeatureDevNavItem[] = [
  { kind: 'leaf', name: 'smart_response', labelKey: 'sidebar.smartResponse' },
  { kind: 'leaf', name: 'kitty_llmops', labelKey: 'admin.kittyLlmopsTab' },
  { kind: 'leaf', name: 'teacher_usage', labelKey: 'sidebar.teacherUsage' },
]

export interface FeatureDevNavVisibilityOptions {
  canViewSettingsSubtab: (subtab: string) => boolean
  featureSmartResponse: boolean
  featureTeacherUsage: boolean
  featureKittyAgent: boolean
}

/** Smart Response admin UI is not production-ready; hide until device flows ship. */
const SMART_RESPONSE_PANEL_READY = false

function canViewLeaf(name: FeatureDevSubtab, options: FeatureDevNavVisibilityOptions): boolean {
  if (!options.canViewSettingsSubtab(name)) {
    return false
  }
  if (name === 'smart_response') {
    if (!SMART_RESPONSE_PANEL_READY) {
      return false
    }
    if (!options.featureSmartResponse) {
      return false
    }
  }
  if (name === 'teacher_usage' && !options.featureTeacherUsage) {
    return false
  }
  if (name === 'kitty_llmops' && !options.featureKittyAgent) {
    return false
  }
  return true
}

export function isFeatureDevSubtab(value: string | null | undefined): value is FeatureDevSubtab {
  return FEATURE_DEV_NAV_ITEMS.some((item) => item.name === value)
}

export function visibleFeatureDevNavItems(
  options: FeatureDevNavVisibilityOptions
): FeatureDevNavItem[] {
  return FEATURE_DEV_NAV_ITEMS.filter((item) => canViewLeaf(item.name, options))
}

export function visibleFeatureDevSubtabs(
  options: FeatureDevNavVisibilityOptions
): FeatureDevSubtab[] {
  return visibleFeatureDevNavItems(options).map((item) => item.name)
}

export function defaultFeatureDevSubtab(
  options: FeatureDevNavVisibilityOptions
): FeatureDevSubtab | null {
  const visible = visibleFeatureDevSubtabs(options)
  return visible[0] ?? null
}

export function resolveFeatureDevSubtab(
  raw: string | null | undefined,
  options: FeatureDevNavVisibilityOptions
): FeatureDevSubtab | null {
  if (typeof raw === 'string' && isFeatureDevSubtab(raw) && canViewLeaf(raw, options)) {
    return raw
  }
  return defaultFeatureDevSubtab(options)
}

export function featureDevSubtabLabelKey(name: FeatureDevSubtab): string | null {
  const item = FEATURE_DEV_NAV_ITEMS.find((entry) => entry.name === name)
  return item?.labelKey ?? null
}

export function featureDevSubtabRequiresCapabilities(subtab: FeatureDevSubtab) {
  return settingsSubtabRequiresCapabilities(subtab)
}

export const LEGACY_FEATURE_DEV_SETTINGS_SUBTABS: readonly string[] = [
  'smart_response',
  'kitty_llmops',
  'teacher_usage',
]

export function hasVisibleFeatureDevNav(options: FeatureDevNavVisibilityOptions): boolean {
  return visibleFeatureDevSubtabs(options).length > 0
}
