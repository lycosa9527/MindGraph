/**
 * Management panel capabilities — mirrors backend admin_panel_permissions.py
 *
 * Access control quick reference (keep in sync with backend):
 * - "super-admin only" → cap in SUPERADMIN_CAPS only; API: require_admin or
 *   require_panel_capability('tab.settings.*')
 * - "school manager only" → cap in SCHOOL_ADMIN_CAPS only
 * - "super-admin OR school manager" → cap in both SUPERADMIN_CAPS and
 *   SCHOOL_ADMIN_CAPS; API: require_panel_capability (preferred) or
 *   require_admin_or_manager_with_rls on legacy routes
 * - UI hiding: settingsSubtabRequiresCapabilities() / canViewFeatureDevTab()
 *
 * Full cookbook: routers/auth/dependencies.py module docstring.
 */
import type { UserRole } from '@/types'

export type AdminCapability =
  | 'panel.access'
  | 'tab.data_center.view'
  | 'tab.data_center.edit'
  | 'tab.school_dashboard.view'
  | 'tab.users.view'
  | 'tab.users.edit'
  | 'tab.organizations.view'
  | 'tab.organizations.edit'
  | 'tab.invites.view'
  | 'tab.invites.edit'
  | 'tab.billing.view'
  | 'tab.billing.edit'
  | 'tab.settings.view'
  | 'tab.settings.edit'
  | 'tab.settings.features'
  | 'tab.settings.roles'
  | 'tab.settings.tokens'
  | 'tab.settings.library'
  | 'tab.settings.database'
  | 'tab.settings.cos'
  | 'tab.settings.performance'
  | 'tab.settings.errors'
  | 'tab.settings.thinking_coins'
  | 'tab.settings.public_dashboard'
  | 'tab.settings.gewe'
  | 'tab.settings.kitty_llmops'
  | 'tab.settings.mindbot'
  | 'tab.settings.mindmate_export'
  | 'tab.settings.smart_response'
  | 'tab.settings.teacher_usage'
  | 'tab.showcase.view'
  | 'tab.showcase.edit'
  | 'tab.showcase.recommend'
  | 'tab.showcase.fields'
  | 'tab.showcase.permissions'
  | 'tab.showcase.dashboard'
  | 'scope.global'
  | 'scope.org'
  | 'scope.invited_orgs'

export interface AdminCapabilitiesPayload {
  role: UserRole | string
  capabilities: AdminCapability[]
  org_ids: number[] | null
  read_only: boolean
  default_org_id: number | null
  panel_access: boolean
}

const SUPERADMIN_CAPS: AdminCapability[] = [
  // All panel + settings capabilities (super-admin only unless also listed below).
  'panel.access',
  'tab.data_center.view',
  'tab.data_center.edit',
  'tab.school_dashboard.view',
  'tab.users.view',
  'tab.users.edit',
  'tab.organizations.view',
  'tab.organizations.edit',
  'tab.invites.view',
  'tab.invites.edit',
  'tab.billing.view',
  'tab.billing.edit',
  'tab.settings.view',
  'tab.settings.edit',
  'tab.settings.features',
  'tab.settings.roles',
  'tab.settings.tokens',
  'tab.settings.library',
  'tab.settings.database',
  'tab.settings.cos',
  'tab.settings.performance',
  'tab.settings.errors',
  'tab.settings.thinking_coins',
  'tab.settings.public_dashboard',
  'tab.settings.gewe',
  'tab.settings.kitty_llmops',
  'tab.settings.mindbot',
  'tab.settings.mindmate_export',
  'tab.settings.smart_response',
  'tab.settings.teacher_usage',
  'tab.showcase.view',
  'tab.showcase.edit',
  'tab.showcase.recommend',
  'tab.showcase.fields',
  'tab.showcase.permissions',
  'tab.showcase.dashboard',
  'scope.global',
]

const PLATFORM_BD_CAPS: AdminCapability[] = [
  'panel.access',
  'tab.data_center.view',
  'tab.data_center.edit',
  'tab.school_dashboard.view',
  'tab.users.view',
  'tab.organizations.view',
  'tab.invites.view',
  'tab.invites.edit',
  'tab.billing.view',
  'tab.showcase.view',
  'tab.showcase.edit',
  'tab.showcase.recommend',
  'tab.showcase.fields',
  'tab.showcase.dashboard',
  'scope.global',
  'scope.invited_orgs',
]

const EXPERT_CAPS: AdminCapability[] = [
  'panel.access',
  // Org management is invite-scoped (created schools only); no global edit.
  'tab.organizations.view',
  'tab.invites.view',
  'tab.invites.edit',
  'scope.invited_orgs',
]

const SCHOOL_ADMIN_CAPS: AdminCapability[] = [
  // School manager: org-scoped member management + school dashboard.
  'panel.access',
  'tab.school_dashboard.view',
  'tab.users.view',
  'tab.users.edit',
  'scope.org',
]

export const ROLE_PANEL_CAPABILITIES: Record<UserRole, AdminCapability[]> = {
  superadmin: SUPERADMIN_CAPS,
  platform_bd: PLATFORM_BD_CAPS,
  expert: EXPERT_CAPS,
  school_admin: SCHOOL_ADMIN_CAPS,
  teacher: [],
  personal_trial: [],
  personal_paid: [],
}

export function fallbackCapabilitiesForRole(role: UserRole | null): AdminCapability[] {
  if (!role) {
    return []
  }
  return ROLE_PANEL_CAPABILITIES[role] ?? []
}

export function roleHasPanelAccess(role: UserRole | null | undefined): boolean {
  return fallbackCapabilitiesForRole(role ?? null).includes('panel.access')
}

/** True when the user has full platform superadmin panel powers (Role Control or env admin). */
export function hasSuperadminPanelAccess(caps: AdminCapability[]): boolean {
  return (
    caps.includes('tab.organizations.edit') &&
    caps.includes('tab.settings.edit') &&
    caps.includes('scope.global')
  )
}

const TAB_EDIT_CAPABILITY: Record<string, AdminCapability> = {
  data_center: 'tab.data_center.edit',
  users: 'tab.users.edit',
  organizations: 'tab.organizations.edit',
  invites: 'tab.invites.edit',
  billing: 'tab.billing.edit',
  feature_dev: 'tab.settings.edit',
  settings: 'tab.settings.edit',
  showcase: 'tab.showcase.edit',
}

export function tabEditCapability(tabKey: string): AdminCapability | null {
  return TAB_EDIT_CAPABILITY[tabKey] ?? null
}

export function tabRequiresCapabilities(tabKey: string): AdminCapability[] {
  const map: Record<string, AdminCapability[]> = {
    data_center: [],
    users: ['tab.users.view', 'scope.global'],
    organizations: ['tab.organizations.view'],
    invites: ['tab.invites.view'],
    billing: ['tab.billing.view'],
    settings: ['tab.settings.view'],
    showcase: ['tab.showcase.view'],
  }
  return map[tabKey] ?? ['panel.access']
}

export function canViewUsersTab(caps: AdminCapability[]): boolean {
  return caps.includes('tab.users.view') && caps.includes('scope.global')
}

export function canViewDataCenterTab(caps: AdminCapability[]): boolean {
  return caps.includes('tab.data_center.view') || caps.includes('tab.school_dashboard.view')
}

/** School managers use the school dashboard sub-view with tab.users.edit, not tab.data_center.edit. */
export function isDataCenterTabReadOnly(caps: AdminCapability[]): boolean {
  if (caps.includes('tab.data_center.edit')) {
    return false
  }
  if (caps.includes('tab.school_dashboard.view') && caps.includes('tab.users.edit')) {
    return false
  }
  return true
}

const FEATURE_DEV_SUBTABS = [
  'smart_response',
  'kitty_llmops',
  'teacher_usage',
  'mindmate_export',
] as const

export function canViewFeatureDevTab(caps: AdminCapability[]): boolean {
  return FEATURE_DEV_SUBTABS.some((subtab) =>
    settingsSubtabRequiresCapabilities(subtab).every((cap) => caps.includes(cap))
  )
}

export function settingsSubtabRequiresCapabilities(subtab: string): AdminCapability[] {
  const map: Record<string, AdminCapability[]> = {
    features: ['tab.settings.features'],
    roles: ['tab.settings.roles'],
    tokens: ['tab.settings.tokens'],
    library: ['tab.settings.library'],
    database: ['tab.settings.database'],
    cos: ['tab.settings.cos'],
    performance: ['tab.settings.performance'],
    errors: ['tab.settings.errors'],
    thinking_coins: ['tab.settings.thinking_coins'],
    public_dashboard: ['tab.settings.public_dashboard'],
    gewe: ['tab.settings.gewe'],
    kitty_llmops: ['tab.settings.kitty_llmops'],
    mindbot: ['tab.settings.mindbot'],
    smart_response: ['tab.settings.smart_response'],
    teacher_usage: ['tab.settings.teacher_usage'],
    mindmate_export: ['tab.settings.mindmate_export'],
  }
  return map[subtab] ?? ['tab.settings.view']
}
