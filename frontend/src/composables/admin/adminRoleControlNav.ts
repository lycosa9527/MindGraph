/**
 * Role-control sub-tab navigation (Settings → Roles).
 */
import type { UserRole } from '@/types'

export type RoleControlTab = Extract<
  UserRole,
  'superadmin' | 'platform_bd' | 'expert' | 'school_admin'
>

export const ROLE_CONTROL_TABS: readonly RoleControlTab[] = [
  'superadmin',
  'platform_bd',
  'expert',
  'school_admin',
]

export function isRoleControlTab(value: unknown): value is RoleControlTab {
  return typeof value === 'string' && ROLE_CONTROL_TABS.includes(value as RoleControlTab)
}
