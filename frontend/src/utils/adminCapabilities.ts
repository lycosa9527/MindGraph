/**
 * Management panel capabilities — mirrors backend admin_panel_permissions.py
 */

import type { UserRole } from '@/types'

export type AdminCapability =
  | 'panel.access'
  | 'tab.data_center.view'
  | 'tab.data_center.edit'
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
  | 'tab.settings.performance'
  | 'tab.settings.gewe'
  | 'tab.settings.kitty_llmops'
  | 'tab.settings.mindbot'
  | 'tab.settings.smart_response'
  | 'tab.settings.teacher_usage'
  | 'scope.global'
  | 'scope.org'

export interface AdminCapabilitiesPayload {
  role: UserRole | string
  capabilities: AdminCapability[]
  org_ids: number[] | null
  read_only: boolean
  default_org_id: number | null
  panel_access: boolean
}

const SUPERADMIN_CAPS: AdminCapability[] = [
  'panel.access',
  'tab.data_center.view',
  'tab.data_center.edit',
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
  'tab.settings.performance',
  'tab.settings.gewe',
  'tab.settings.kitty_llmops',
  'tab.settings.mindbot',
  'tab.settings.smart_response',
  'tab.settings.teacher_usage',
  'scope.global',
]

const PLATFORM_BD_CAPS: AdminCapability[] = [
  'panel.access',
  'tab.data_center.view',
  'tab.data_center.edit',
  'tab.users.view',
  'tab.organizations.view',
  'tab.invites.view',
  'tab.invites.edit',
  'tab.billing.view',
  'scope.global',
]

const EXPERT_CAPS: AdminCapability[] = [
  'panel.access',
  'tab.invites.view',
  'tab.invites.edit',
]

const SCHOOL_ADMIN_CAPS: AdminCapability[] = [
  'panel.access',
  'tab.data_center.view',
  'tab.users.view',
  'tab.users.edit',
  'tab.invites.view',
  'tab.invites.edit',
  'tab.settings.view',
  'tab.settings.mindbot',
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

const TAB_EDIT_CAPABILITY: Record<string, AdminCapability> = {
  data_center: 'tab.data_center.edit',
  users: 'tab.users.edit',
  organizations: 'tab.organizations.edit',
  invites: 'tab.invites.edit',
  billing: 'tab.billing.edit',
  settings: 'tab.settings.edit',
}

export function tabEditCapability(tabKey: string): AdminCapability | null {
  return TAB_EDIT_CAPABILITY[tabKey] ?? null
}

export function tabRequiresCapabilities(tabKey: string): AdminCapability[] {
  const map: Record<string, AdminCapability[]> = {
    data_center: ['tab.data_center.view'],
    users: ['tab.users.view', 'scope.global'],
    organizations: ['tab.organizations.view'],
    invites: ['tab.invites.view'],
    billing: ['tab.billing.view'],
    settings: ['tab.settings.view'],
  }
  return map[tabKey] ?? ['panel.access']
}

export function settingsSubtabRequiresCapabilities(subtab: string): AdminCapability[] {
  const map: Record<string, AdminCapability[]> = {
    features: ['tab.settings.features'],
    roles: ['tab.settings.roles'],
    tokens: ['tab.settings.tokens'],
    library: ['tab.settings.library'],
    database: ['tab.settings.database'],
    performance: ['tab.settings.performance'],
    gewe: ['tab.settings.gewe'],
    kitty_llmops: ['tab.settings.kitty_llmops'],
    mindbot: ['tab.settings.mindbot'],
    smart_response: ['tab.settings.smart_response'],
    teacher_usage: ['tab.settings.teacher_usage'],
  }
  return map[subtab] ?? ['tab.settings.view']
}
