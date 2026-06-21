/**
 * 系统设置 sidebar navigation (top-level panel tab).
 */
import { settingsSubtabRequiresCapabilities } from '@/utils/adminCapabilities'

export type SettingsSubtab =
  | 'features'
  | 'roles'
  | 'database'
  | 'performance'
  | 'library'
  | 'gewe'
  | 'errors'
  | 'thinking_coins'

export interface SettingsNavLeafItem {
  kind: 'leaf'
  name: SettingsSubtab
  labelKey: string
}

export type SettingsNavItem = SettingsNavLeafItem

export const SETTINGS_NAV_ITEMS: readonly SettingsNavItem[] = [
  { kind: 'leaf', name: 'features', labelKey: 'admin.featuresTab' },
  { kind: 'leaf', name: 'roles', labelKey: 'admin.roleControl' },
  { kind: 'leaf', name: 'database', labelKey: 'admin.database.tab' },
  { kind: 'leaf', name: 'performance', labelKey: 'admin.performance.tab' },
  { kind: 'leaf', name: 'errors', labelKey: 'admin.errors.tab' },
  { kind: 'leaf', name: 'thinking_coins', labelKey: 'thinkingCoins.admin.tab' },
  { kind: 'leaf', name: 'library', labelKey: 'admin.library' },
  { kind: 'leaf', name: 'gewe', labelKey: 'admin.geweWechat' },
]

export function isSettingsSubtab(value: string | null | undefined): value is SettingsSubtab {
  return SETTINGS_NAV_ITEMS.some((item) => item.name === value)
}

export function defaultSettingsSubtab(): SettingsSubtab {
  return 'roles'
}

export function settingsSubtabLabelKey(name: SettingsSubtab): string | null {
  const item = SETTINGS_NAV_ITEMS.find((entry) => entry.name === name)
  return item?.labelKey ?? null
}

export interface SettingsNavVisibilityOptions {
  canViewSettingsSubtab: (subtab: string) => boolean
  featureGewe: boolean
  featureLibrary: boolean
}

function canViewLeaf(name: SettingsSubtab, options: SettingsNavVisibilityOptions): boolean {
  if (!options.canViewSettingsSubtab(name)) {
    return false
  }
  if (name === 'gewe' && !options.featureGewe) {
    return false
  }
  if (name === 'library' && !options.featureLibrary) {
    return false
  }
  return true
}

export function visibleSettingsNavItems(
  options: SettingsNavVisibilityOptions
): SettingsNavItem[] {
  return SETTINGS_NAV_ITEMS.filter((item) => canViewLeaf(item.name, options))
}

export function visibleSettingsSubtabs(options: SettingsNavVisibilityOptions): SettingsSubtab[] {
  return visibleSettingsNavItems(options).map((item) => item.name)
}

export function settingsSubtabCapabilities(subtab: SettingsSubtab) {
  return settingsSubtabRequiresCapabilities(subtab)
}
